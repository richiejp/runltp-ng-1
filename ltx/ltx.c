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

struct ltx_cursor {
	uint8_t *ptr;
	size_t left;
};

struct ltx_str {
	const size_t len;
	const char *const data;
};

enum msgp_fmt {
	msgp_fixint0 = 0x00,
	msgp_fixing127 = 0x7f,
	msgp_fixarray0 = 0x90,
	msgp_fixarray15 = 0x9f,
	msgp_fixstr0 = 0xa0,
	msgp_fixstr31 = 0xbf,
	msgp_nil = 0xc0,
	msgp_bin8 = 0xc4,
	msgp_bin32 = 0xc6,
	msgp_uint8 = 0xcc,
	msgp_uint64 = 0xcf,
	msgp_str8 = 0xd9,
	msgp_str16 = 0xda,
	msgp_str32 = 0xdb
};

enum ltx_msg_types {
	ltx_msg_ping,
	ltx_msg_pong,
	ltx_msg_env,
	ltx_msg_exec,
	ltx_msg_log,
	ltx_msg_result,
	ltx_msg_get_file,
	ltx_msg_set_file,
	ltx_msg_data,
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

__attribute__((nonnull, warn_unused_result))
static uint8_t ltx_cur_pop(struct ltx_cursor *const self)
{
	self->left--;
	self->ptr++;

	return self->ptr[0];
}

__attribute__((nonnull, warn_unused_result))
static uint8_t *ltx_cur_take(struct ltx_cursor *const self, size_t len)
{
	uint8_t *ptr = self->ptr;

	self->left -= len;
	self->ptr += len;

	return ptr;
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

__attribute__((warn_unused_result))
static uint64_t ltx_gettime(void)
{
	struct timespec ts;

#ifdef CLOCK_MONOTONIC_RAW
	clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
#else
	clock_gettime(CLOCK_MONOTONIC, &ts);
#endif

	return ts.tv_sec * 1000000000 + ts.tv_nsec;
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

	head[head_len++] = ltx_fixarr(4);
	head[head_len++] = ltx_msg_log;
	head[head_len++] = table_id;

	memcpy(head + head_len, ltx_uint64(ltx_gettime()), sizeof(uint64_t) + 1);
	head_len += sizeof(uint64_t) + 1;

	if (text_len < 32) {
		/* fixstr[buf->used] = "...*/
		head[head_len++] = msgp_fixstr0 + text_len;
		memmove(head + head_len, text, text_len);
	} else if (text_len < 256) {
		/* str8[buf->used] = "...*/
		head[head_len++] = msgp_str8;
		head[head_len++] = text_len;
		memmove(head + head_len, text, text_len);
	} else {
		/* str16[buf->used] = "...*/
		head[head_len++] = msgp_str16;
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

__attribute__((nonnull, warn_unused_result))
static size_t ltx_read_size(struct ltx_cursor *const cur, const size_t len)
{
	uint8_t *d = ltx_cur_take(cur, len);
	size_t res = 0;

	for (unsigned i = 0; i < len; i++) {
		res <<= i * 8;
		res += d[i];
	}

	return res;
}

__attribute__((nonnull, warn_unused_result))
static struct ltx_str ltx_read_str(struct ltx_cursor *cur)
{
	size_t l = 0, w = 0;
	enum msgp_fmt fmt = ltx_cur_pop(cur);

	switch (fmt) {
	case msgp_fixstr0 ... msgp_fixstr31:
		l = fmt - msgp_fixstr0;
		break;
	case msgp_str8 ... msgp_str32:
		w = 1 + fmt - msgp_str8;
		break;
	default:
		ltx_assert(0, "Not a string fmt: '%x'", fmt);
	}

	if (w > cur->left)
		goto out_of_data;
	if (w)
		l = ltx_read_size(cur, w);
	if (l > cur->left)
		goto out_of_data;

	return (struct ltx_str) {
		.len = l,
		.data = (const char *const)ltx_cur_take(cur, l)
	};

out_of_data:
	return (struct ltx_str) {
		.len = 0,
		.data = NULL,
	};
}

static void ltx_write_str(

static int process_exec_msg(struct ltx_cursor *cur, const uint8_t args_n)
{
	uint8_t table_id;
	char cpath[256];
	pid_t child;
	int pipefd[2];

	table_id = ltx_cur_pop(cur);
	ltx_assert(table_id < 0x7f, "Exec: (table_id = %u) > 127", table_id);

	if (!cur->left)
		return 0;

	struct ltx_str path = ltx_read_str(cur);

	if (!path.data)
		return 0;

	ltx_out_q((uint8_t []){ ltx_fixarr(args_n + 1), ltx_msg_exec }, 2);
	ltx_out_q((uint8_t *)path.data, path.len);

	ltx_assert(args_n == 2, "Exec: argsv not implemented");

	LTX_EXP_0(pipe2(pipefd, O_CLOEXEC));
	childs[table_id].fd = pipefd[0];
	ltx_epoll_add(childs + table_id, EPOLLOUT);
	child = LTX_EXP_POS(fork());

	if (child) {
		close(pipefd[1]);
		childs[table_id].pid = child;
		child_pids[table_id] = child;
		return 1;
	}

	LTX_EXP_POS(dup2(pipefd[1], STDERR_FILENO));
	LTX_EXP_POS(dup2(pipefd[1], STDOUT_FILENO));

	memcpy(cpath, path.data, path.len);
	cpath[path.len] = '\0';
	LTX_EXP_0(execv(cpath, (char *const[]){ cpath, NULL }));
	__builtin_unreachable();
}

static int process_get_file_msg(struct ltx_cursor *cur)
{
	struct ltx_str path = ltx_read_str(cur);

	if (path.data == NULL)
		return 0;

	ltx_out_q((uint8_t []){ ltx_fixarr(2), ltx_msg_get_file, }, 2);
}

static void process_msgs(void)
{
	struct ltx_cursor outer_cur = {
		.ptr = ltx_buf_start(&in_buf),
		.left = in_buf.used,
	};

	while (outer_cur.left > 1) {
		struct ltx_cursor cur = outer_cur;
		size_t ret;
		enum msgp_fmt msg_fmt = ltx_cur_pop(&cur);

		ltx_assert(msg_fmt & msgp_fixarray0,
			   "Message should start with fixarray, not %x",
			   msg_fmt);

		const uint8_t msg_arr_len = msg_fmt - msgp_fixarray0;
		const uint8_t msg_type = ltx_cur_pop(&cur);

		switch (msg_type) {
		case ltx_msg_ping:
			ltx_assert(msg_arr_len == 1,
				   "Ping: (msg_arr_len = %u) != 1",
				   msg_arr_len);

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

			if (!process_exec_msg(&cur, msg_arr_len))
				goto out;

			break;
		case ltx_msg_log:
			ltx_assert(!ltx_msg_log, "Not handled by executor");
		case ltx_msg_result:
			ltx_assert(!ltx_msg_result, "Not handled by executor");
		case ltx_msg_get_file:
			ltx_assert(msg_arr_len == 2,
				   "Get File: (msg_arr_len = %u) != 2",
				   msg_arr_len);

			if (!process_get_file_msg(cur))
				goto out;
		case ltx_msg_set_file:
			ltx_assert(!ltx_msg_set_file, "Not implemented");
		case ltx_msg_data:
			ltx_assert(!ltx_msg_data, "Not implemented");
		default:
			ltx_assert(msg_type < ltx_msg_max,
				   "(msg_type = %u) >= ltx_msg_max",
				   msg_type);
		}

		outer_cur = cur;

		if (out_buf.used > BUFSIZ / 4)
			drain_write_buf();
	}

out:
	memmove(in_buf.data, ltx_buf_start(&in_buf), in_buf.used);
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
					ltx_fixarr(5),
					ltx_msg_result,
					table_id
			}, 3);

			ltx_out_q(ltx_uint64(ltx_gettime()), sizeof(uint64_t) + 1);

			ltx_out_q((uint8_t[]){
					(uint8_t)si[i].ssi_code,
					(uint8_t)si[i].ssi_status
			}, 2);
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
