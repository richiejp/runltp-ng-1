#define _GNU_SOURCE

#include <execinfo.h>
#include <errno.h>
#include <endian.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <poll.h>
#include <signal.h>
#include <time.h>
#include <limits.h>

#include <sys/types.h>
#include <sys/wait.h>
#include <sys/uio.h>
#include <sys/epoll.h>
#include <sys/signalfd.h>

#define VERSION "0.0.1-dev"

#define LTX_POS ((struct ltx_pos){ __FILE__, __func__, __LINE__ })
#define LTX_LOG(fmt, ...) ltx_log(LTX_POS, fmt, ##__VA_ARGS__)

#define ltx_assert(expr, fmt, ...) do {				\
	if (expr)							\
		break;							\
									\
	ltx_log(LTX_POS,						\
		"Fatal assertion '" #expr "': " fmt,			\
		##__VA_ARGS__);						\
									\
	void *buf[BUFSIZ];						\
	int i, nptrs = backtrace(buf, BUFSIZ);				\
	for (i = 0; i < nptrs; i++)					\
		fprintf(stderr, "\t%p\n", buf[i]);			\
	exit(1);							\
} while (0);

#define LTX_EXP_FD(expr)			\
	ltx_exp_fd(LTX_POS, expr, #expr)
#define LTX_EXP_0(expr)				\
	ltx_exp_0(LTX_POS, expr, #expr)
#define LTX_EXP_POS(expr)			\
	ltx_exp_pos(LTX_POS, expr, #expr)

struct ltx_pos {
	const char *const file;
	const char *const func;
	const int line;
};

struct ltx_buf {
	size_t off;
	size_t used;
	uint8_t data[BUFSIZ];
};

enum ltx_msg_types {
	ltx_msg_ping,
	ltx_msg_pong,
	ltx_msg_env,
	ltx_msg_exec,
	ltx_msg_log,
	ltx_msg_result,
	ltx_msg_max,
};

enum ltx_ev_source_type {
	ltx_ev_io,
	ltx_ev_child_io,
	ltx_ev_signal
};

struct ltx_ev_source {
	enum ltx_ev_source_type type;
	uint8_t table_id;
	int fd;
	pid_t pid;
};

static const uint8_t ltx_nil = 0xc0;

static struct ltx_ev_source ltx_in = {
	.type = ltx_ev_io,
	.fd = STDIN_FILENO,
};
static struct ltx_buf in_buf;

static struct ltx_ev_source ltx_out = {
	.type = ltx_ev_io,
	.fd = STDOUT_FILENO,
};
static int out_fd_blocked;
static struct ltx_buf out_buf;

static struct ltx_ev_source ltx_sig = {
	.type = ltx_ev_signal
};
static int ep_fd;
static pid_t ltx_pid;

static struct ltx_ev_source childs[0x7f];
static uint32_t child_pids[0x7f];

__attribute__((const, warn_unused_result))
static size_t ltx_min_sz(const size_t a, const size_t b)
{
	return a < b ? a : b;
}

__attribute__((const, warn_unused_result))
static uint8_t ltx_fixarr(const uint8_t len)
{
	return 0x90 + len;
}

__attribute__((warn_unused_result))
static uint8_t *ltx_uint64(const uint64_t i)
{
	static uint8_t buf[9];

	buf[0] = 0xcf;

	for (int j = 1; j < 9; j++)
		buf[j] = (uint8_t)(i >> (64 - 8*j));

	return buf;
}

__attribute__((pure, nonnull, warn_unused_result))
static uint8_t *ltx_buf_start(struct ltx_buf *const self)
{
	return self->data + self->off;
}

__attribute__((pure, nonnull, warn_unused_result))
static uint8_t *ltx_buf_end(struct ltx_buf *const self)
{
	return ltx_buf_start(self) + self->used;
}

__attribute__((pure, nonnull, warn_unused_result))
static size_t ltx_buf_avail(const struct ltx_buf *const self)
{
	return BUFSIZ - (self->off + self->used);
}

__attribute__((nonnull))
static void ltx_fmt(const struct ltx_pos pos,
		    struct ltx_buf *const buf,
		    const char *const fmt,
		    va_list ap)
{
	buf->used += snprintf((char *)ltx_buf_end(buf), ltx_buf_avail(buf) - 2,
			      "[%s:%s:%i] ", pos.file, pos.func, pos.line);
	buf->used += vsnprintf((char *)ltx_buf_end(buf), ltx_buf_avail(buf) - 2, fmt, ap);

	memcpy(ltx_buf_end(buf), "\n\0", 2);
	buf->used++;
}

__attribute__((nonnull))
static void ltx_log_head(struct ltx_buf *const buf,
			 const uint8_t table_id,
			 const size_t reserved,
			 const size_t text_len)
{
	uint8_t *const text = ltx_buf_end(buf) - text_len;
	uint8_t *const head = text - reserved;
	size_t head_len = 0;

	head[head_len++] = ltx_fixarr(3);
	head[head_len++] = ltx_msg_log;
	head[head_len++] = table_id;

	if (text_len < 32) {
		/* fixstr[buf->used] = "...*/
		head[head_len++] = 0xa0 + text_len;
		memmove(head + head_len, text, text_len);
	} else if (text_len < 256) {
		/* str8[buf->used] = "...*/
		head[head_len++] = 0xd9;
		head[head_len++] = text_len;
		memmove(head + head_len, text, text_len);
	} else {
		/* str16[buf->used] = "...*/
		head[head_len++] = 0xda;
		head[head_len++] = text_len >> 8;
		head[head_len] = text_len;
	}

	buf->used -= reserved - head_len;
}

__attribute__((nonnull, format(printf, 2, 3)))
static void ltx_log(const struct ltx_pos pos, const char *const fmt, ...)
{
	struct ltx_buf msg = { .off = 32, .used = 0 };
	va_list ap;
	ssize_t res;

	va_start(ap, fmt);
	ltx_fmt(pos, &msg, fmt, ap);
	va_end(ap);

	res = write(STDERR_FILENO, ltx_buf_start(&msg), msg.used);

	if (ltx_pid != getpid())
		return;

	msg.off = 0;
	msg.used += 32;
	ltx_log_head(&msg, ltx_nil, 32, msg.used - 32);

	while (msg.used) {
		res = write(ltx_out.fd, ltx_buf_start(&msg), msg.used);
		if (res < 0)
			break;

		msg.off += res;
		msg.used -= res;
	}
}

__attribute__((nonnull, warn_unused_result))
static int ltx_exp_fd(const struct ltx_pos pos,
		      const int fd,
		      const char *const expr)
{
	if (fd > -1)
		return fd;

	ltx_log(pos, "Invalid FD: %s = %d: %s", expr, fd, strerrorname_np(errno));

	exit(1);
}

__attribute__((nonnull))
static void ltx_exp_0(const struct ltx_pos pos,
		      const int ret,
		      const char *const expr)
{
	if (!ret)
		return;

	ltx_log(pos, "Not Zero: %s = %d: %s", expr, ret, strerrorname_np(errno));

	exit(1);
}

__attribute__((nonnull))
static int ltx_exp_pos(const struct ltx_pos pos,
		       const int ret,
		       const char *const expr)
{
	if (ret > -1)
		return ret;

	ltx_log(pos, "Not positive: %s = %d: %s", expr, ret, strerrorname_np(errno));

	exit(1);
}

__attribute__((warn_unused_result))
static uint64_t ltx_gettime(void)
{
	struct timespec ts;

#ifdef CLOCK_MONOTONIC_RAW
	LTX_EXP_0(clock_gettime(CLOCK_MONOTONIC_RAW, &ts));
#else
	LTX_EXP_0(clock_gettime(CLOCK_MONOTONIC, &ts));
#endif

	return ts.tv_sec * 1000000000 + ts.tv_nsec;
}

static void ltx_out_q(const uint8_t *const data, const size_t len)
{
	ltx_assert(ltx_buf_avail(&out_buf) >= len,
		   "%zu < %zu", ltx_buf_avail(&out_buf), len);

	memcpy(ltx_buf_end(&out_buf), data, len);

	out_buf.used += len;
}

static void ltx_epoll_add(struct ltx_ev_source *ev_src, const uint32_t events)
{
	struct epoll_event ev = {
		.events = events,
		.data = (epoll_data_t){ .ptr = ev_src },
	};

	LTX_EXP_0(epoll_ctl(ep_fd, EPOLL_CTL_ADD, ev_src->fd, &ev));
}

static void fill_read_buf(void)
{
	ltx_assert(ltx_buf_avail(&in_buf) > 0, "read buffer full");

	const int ilen = LTX_EXP_POS(read(ltx_in.fd,
					  ltx_buf_end(&in_buf),
					  ltx_buf_avail(&in_buf)));
	in_buf.used += ilen;
}

static void drain_write_buf(void)
{
	while (out_buf.used) {
		const int olen = write(ltx_out.fd, ltx_buf_start(&out_buf), out_buf.used);

		if (olen < 0 && errno == EAGAIN) {
			out_fd_blocked = 1;
			break;
		}

		ltx_assert(olen > -1,
			   "write(out_fd, out_buf.data, %zu): %s",
			   out_buf.used, strerrorname_np(errno));

		out_buf.off += olen;
		out_buf.used -= olen;
	}

	if (out_buf.used) {
		memmove(out_buf.data,
			ltx_buf_start(&out_buf),
			out_buf.used);
	}

	out_buf.off = 0;
}

static int process_exec_msg(const uint8_t args_n,
			    const uint8_t *const data, const size_t len)
{
	uint8_t table_id;
	size_t c = 0;
	uint8_t path_fmt, path_len;
	const uint8_t *path;
	char cpath[256];
	pid_t child;
	int pipefd[2];

	if (c == len)
		return 0;

	table_id = data[c++];
	ltx_assert(table_id < 0x7f, "Exec: (table_id = %u) > 127", table_id);

	if (c == len)
		return 0;

	path_fmt = data[c++];
	switch (path_fmt) {
	case 0xa0 ... 0xbf:
		path_len = path_fmt - 0xa0;
		ltx_assert(path_len, "Exec: Can't have empty path");

		if (c == len)
			return 0;

		path = &data[c];
		break;
	case 0xd9:
		if (c == len)
			return 0;

		path_len = data[c++];
		ltx_assert(path_len < 31, "Exec: Path could not fit in fixstr");

		if (c == len)
			return 0;

		path = &data[c];
		break;
	default:
		ltx_assert(0, "Exec: Path format = %u; not fixstr or str8",
			   data[1]);
	}

	dprintf(STDERR_FILENO, "Exec: c=%zu, path_len=%u, len=%zu\n", c, path_len, len);
	c += path_len;
	if (c > len)
		return 0;

	ltx_out_q((uint8_t []){ ltx_fixarr(args_n + 1), ltx_msg_exec }, 2);
	ltx_out_q(data, len);

	ltx_assert(args_n == 2, "Exec: argsv not implemented");

	LTX_EXP_0(pipe2(pipefd, O_CLOEXEC));
	childs[table_id].fd = pipefd[0];
	ltx_epoll_add(childs + table_id, EPOLLOUT);
	child = LTX_EXP_POS(fork());

	if (child) {
		close(pipefd[1]);
		dprintf(STDERR_FILENO, "Started %d\n", child);
		childs[table_id].pid = child;
		child_pids[table_id] = child;
		return c;
	}

	LTX_EXP_POS(dup2(pipefd[1], STDERR_FILENO));
	LTX_EXP_POS(dup2(pipefd[1], STDOUT_FILENO));

	memcpy(cpath, path, path_len);
	cpath[path_len] = '\0';
	LTX_EXP_0(execv(cpath, (char *const[]){ cpath, NULL }));
	__builtin_unreachable();
}

static void process_msgs(void)
{
	while (in_buf.used > 1) {
		const uint8_t *const data = ltx_buf_start(&in_buf);
		size_t ret, len = 0;

		ltx_assert(data[0] & 0x90,
			   "Message should start with fixarray, not %x",
			   data[0]);

		const uint8_t msg_arr_len = data[len++] & 0x0f;
		const uint8_t msg_type = data[len++];

		switch (msg_type) {
		case ltx_msg_ping:
			ltx_assert(msg_arr_len == 1, "Ping: (msg_arr_len = %u) != 1", msg_arr_len);
			ltx_out_q((uint8_t[]){ ltx_fixarr(1), ltx_msg_ping },
				  2);

			ltx_out_q((uint8_t[]){ ltx_fixarr(2), ltx_msg_pong },
				  2);
			ltx_out_q(ltx_uint64(ltx_gettime()), 9);

			break;
		case ltx_msg_pong:
			ltx_assert(!ltx_msg_pong, "Not handled by executor");
		case ltx_msg_env:
			ltx_assert(!ltx_msg_env, "Not implemented");
		case ltx_msg_exec:
			ltx_assert(msg_arr_len > 2,
				   "Exec: (msg_arr_len = %u) < 3",
				   msg_arr_len);

			dprintf(STDERR_FILENO, "start exec msg\n");
			ret = process_exec_msg(msg_arr_len - 1,
					       data + len,
					       in_buf.used - len);
			if (!ret) {
				len = 0;
				goto out;
			}

			len += ret;
			break;
		case ltx_msg_log:
			ltx_assert(!ltx_msg_log, "Not handled by executor");
		case ltx_msg_result:
			ltx_assert(!ltx_msg_result, "Not handled by executor");
		default:
			ltx_assert(msg_type < ltx_msg_max,
				   "(msg_type = %u) >= ltx_msg_max",
				   msg_type);
		}

		in_buf.off += len;
		in_buf.used -= len;

		if (out_buf.used > BUFSIZ / 4)
			drain_write_buf();
	}

out:
	memmove(in_buf.data, ltx_buf_start(&in_buf), in_buf.used);
	in_buf.off = 0;
}

static int process_event(const struct epoll_event *const ev)
{
	struct ltx_ev_source *ev_src = ev->data.ptr;
	struct signalfd_siginfo si[0x7f];
	ssize_t len, sig_n;
	uint8_t table_id;

	if (ev_src->type == ltx_ev_io) {
		if (ev->events & EPOLLIN)
			fill_read_buf();

		if (ev->events & EPOLLOUT)
			out_fd_blocked = 0;

		if (ev->events & EPOLLHUP)
			return 1;

		return 0;
	}

	if (ev_src->type == ltx_ev_signal) {
		len = LTX_EXP_POS(read(ev_src->fd, si, sizeof(si[0]) * 0x7f));
		sig_n = len / sizeof(si[0]);

		ltx_assert(sig_n * (ssize_t)sizeof(si[0]) == len,
			   "signalfd reads not atomic?");

		for (int i = 0; i < sig_n; i++) {
			for (table_id = 0; table_id < 0x7f; table_id++) {
				if (child_pids[table_id] == si[i].ssi_pid)
					break;
			}

			ltx_assert(table_id < 0x7f,
				   "PID not found: %d", si[i].ssi_pid);

			ltx_out_q((uint8_t[]){
					ltx_fixarr(4),
					ltx_msg_result,
					table_id,
					(uint8_t)si[i].ssi_code,
					(uint8_t)si[i].ssi_status
			}, 5);
		}
	} else if (ev->events & EPOLLHUP || ev->events & EPOLLOUT) {
		out_buf.used += 32;
		len = LTX_EXP_POS(read(ev_src->fd,
				       ltx_buf_end(&out_buf),
				       ltx_min_sz(1024, ltx_buf_avail(&out_buf))));

		if (len) {
			out_buf.used += len;
			ltx_log_head(&out_buf, ev_src->table_id, 32, len);
		} else {
			out_buf.used -= 32;
			close(ev_src->fd);
		}
	}

	if (out_buf.used > BUFSIZ / 4)
		drain_write_buf();

	return 0;
}

static void event_loop(void)
{
	const int maxevents = 128;
	int stop = 0;
	struct epoll_event events[maxevents];
	sigset_t mask;

	for (int i = 0; i < 0x7f; i++) {
		childs[i].type = ltx_ev_child_io;
		childs[i].table_id = i;
	}

	sigemptyset(&mask);
	sigaddset(&mask, SIGCHLD);
	LTX_EXP_0(sigprocmask(SIG_BLOCK, &mask, NULL));
	ltx_sig.fd = LTX_EXP_FD(signalfd(-1, &mask, SFD_CLOEXEC));

	fcntl(ltx_out.fd, F_SETFL, O_NONBLOCK);

	ep_fd = LTX_EXP_FD(epoll_create1(EPOLL_CLOEXEC));

	ltx_epoll_add(&ltx_in, EPOLLIN);
	ltx_epoll_add(&ltx_out, EPOLLOUT | EPOLLET);
	ltx_epoll_add(&ltx_sig, EPOLLIN);

	while (!stop) {
		const int eventsn =
			LTX_EXP_POS(epoll_wait(ep_fd, events, maxevents, 100));

		for (int i = 0; i < eventsn; i++)
			stop += process_event(events + i);

		if (out_buf.used && !out_fd_blocked)
			drain_write_buf();

		if (in_buf.used < 2)
			continue;

		process_msgs();

		if (out_buf.used && !out_fd_blocked)
			drain_write_buf();
	}
}

int main(void)
{
	ltx_pid = getpid();
	LTX_LOG("Linux Test Executor " VERSION);

	event_loop();

	LTX_LOG("Exiting");
	return 0;
}
