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
#include <time.h>
#include <limits.h>

#include <sys/types.h>
#include <sys/wait.h>
#include <sys/uio.h>
#include <sys/epoll.h>

#define VERSION "0.0.1-dev"
#define LTX_IOV_MAX 3

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
	size_t used;
	uint8_t data[BUFSIZ];
};

enum ltx_msg_types {
	ltx_msg_ping,
	ltx_msg_pong,
	ltx_msg_env,
	ltx_msg_exec,
	ltx_msg_log,
	ltx_msg_max,
};

static const uint8_t ltx_nil = 0xc0;

static const int in_fd = STDIN_FILENO;
static struct ltx_buf in_buf;
static const int out_fd = STDOUT_FILENO;
static int out_fd_blocked;
static struct ltx_buf out_buf;
static int ep_fd;
static pid_t ltx_pid;

const static pid_t child_fd_off = 100;
static pid_t childs[0x7f];

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
static uint8_t *ltx_buf_end(struct ltx_buf *const self)
{
	return self->data + self->used;
}

__attribute__((pure, nonnull, warn_unused_result))
static size_t ltx_buf_avail(const struct ltx_buf *const self)
{
	return BUFSIZ - self->used;
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

__attribute__((nonnull, warn_unused_result))
static size_t ltx_log_msg(struct iovec *const iov, const struct ltx_buf *const buf)
{
	uint8_t *const head = iov[0].iov_base;
	size_t len = 0;

	head[len++] = ltx_fixarr(3);
	head[len++] = ltx_msg_log;
	head[len++] = ltx_nil;

	if (buf->used < 32) {
		/* fixstr[buf->used] = "...*/
		head[len++] = 0xa0 + buf->used;
	} else if (buf->used < 256) {
		/* str8[buf->used] = "...*/
		head[len++] = 0xd9;
		head[len++] = buf->used;
	} else {
		/* str16[buf->used] = "...*/
		head[len++] = 0xda;
		head[len++] = buf->used >> 8;
		head[len++] = buf->used;
	}

	iov[0].iov_len = len;

	/* ...buf->data" } */
	iov[1].iov_base = (void *)buf->data;
	iov[1].iov_len = buf->used;

	return 2;
}

__attribute__((nonnull, format(printf, 2, 3)))
static void ltx_log(const struct ltx_pos pos, const char *const fmt, ...)
{
	struct ltx_buf head = { .used = 0 };
	struct ltx_buf msg = { .used = 0 };
	va_list ap;
	struct iovec iov[LTX_IOV_MAX];
	size_t iov_len, iov_i;
	ssize_t res;

	va_start(ap, fmt);
	ltx_fmt(pos, &msg, fmt, ap);
	va_end(ap);

	res = write(STDERR_FILENO, msg.data, msg.used);

	if (ltx_pid != getpid())
		return;

	iov[0].iov_base = head.data;
	iov_len = ltx_log_msg(iov, &msg);
	iov_i = 0;

	while (1) {
		res = writev(out_fd, iov + iov_i, iov_len);
		if (res < 0)
			break;

		while ((size_t)res > iov[iov_i].iov_len) {
			res -= iov[iov_i].iov_len;
			iov_i++;
		}

		if ((size_t)res == iov[iov_i].iov_len)
			break;

		iov[iov_i].iov_len -= res;
		iov[iov_i].iov_base += res;
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

static void ltx_epoll_add(const int fd, const uint32_t events)
{
	struct epoll_event ev = {
		.events = events,
		.data = (epoll_data_t){ .fd = fd },
	};

	LTX_EXP_0(epoll_ctl(ep_fd, EPOLL_CTL_ADD, fd, &ev));
}

static void fill_read_buf(void)
{
	ltx_assert(ltx_buf_avail(&in_buf) > 0, "read buffer full");

	const int ilen = LTX_EXP_POS(read(in_fd,
					  ltx_buf_end(&in_buf),
					  ltx_buf_avail(&in_buf)));
	in_buf.used += ilen;
}

static void drain_write_buf(void)
{
	while (out_buf.used) {
		const int olen = write(out_fd, out_buf.data, out_buf.used);

		if (olen < 0 && errno == EAGAIN) {
			out_fd_blocked = 1;
			return;
		}

		ltx_assert(olen > -1,
			   "write(out_fd, out_buf.data, %zu): %s",
			   out_buf.used, strerrorname_np(errno))

		out_buf.used -= olen;

		memmove(out_buf.data,
			out_buf.data + olen,
			out_buf.used);
	}
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
	int pipefd[2], child_out;

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
		ltx_assert(path_len > 31, "Exec: Path could fit in fixstr");

		if (c == len)
			return 0;

		path = &data[c];
		break;
	default:
		ltx_assert(0, "Exec: Path format = %u; not fixstr or str8",
			   data[1]);
	}

	c += path_len;
	if (c >= len)
		return 0;

	ltx_assert(args_n == 2, "Exec: argsv not implemented");

	LTX_EXP_0(pipe2(pipefd, O_CLOEXEC));
	child_out = LTX_EXP_FD(dup2(pipefd[0], child_fd_off + table_id));
	ltx_epoll_add(child_out, EPOLLOUT);
	child = LTX_EXP_POS(fork());

	if (child) {
		close(pipefd[1]);
		childs[table_id] = child;
		return c;
	}

	LTX_EXP_POS(dup2(pipefd[1], STDERR_FILENO));
	LTX_EXP_POS(dup2(pipefd[1], STDOUT_FILENO));

	memcpy(cpath, path, path_len);
	cpath[path_len] = '\0';
	LTX_EXP_0(execv(cpath, (char *const[]){}));
	__builtin_unreachable();
}

static void process_msgs(void)
{
	const size_t used = in_buf.used;
	size_t consumed = 0;

	while (used - consumed > 1) {
		const uint8_t *const data = in_buf.data + consumed;
		size_t msg_consumed = 0;

		ltx_assert(data[0] & 0x90,
			   "Message should start with fixarray, not %x",
			   data[0]);

		const uint8_t msg_arr_len = data[0] & 0x0f;
		const uint8_t msg_type = data[1];

		switch (msg_type) {
		case ltx_msg_ping:
			ltx_assert(msg_arr_len == 1, "Ping: (msg_arr_len = %u) != 1", msg_arr_len);
			ltx_out_q((uint8_t[]){ ltx_fixarr(1), ltx_msg_ping },
				  2);
			msg_consumed = 2;

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

			msg_consumed = process_exec_msg(msg_arr_len - 1,
							data + 2,
							used - consumed - 2);
			if (!msg_consumed)
				goto out;

			break;
		case ltx_msg_log:
			ltx_assert(!ltx_msg_log, "Not handled by executor");
		default:
			ltx_assert(msg_type < ltx_msg_max,
				   "(msg_type = %u) >= ltx_msg_max",
				   msg_type);
		}

		consumed += msg_consumed;

		if (out_buf.used > BUFSIZ / 4)
			drain_write_buf();
	}

out:
	in_buf.used -= consumed;
	memmove(in_buf.data, in_buf.data + consumed, in_buf.used);
}

static void event_loop(void)
{
	const int maxevents = 2;
	int stop = 0;
	struct epoll_event events[maxevents];

	fcntl(out_fd, F_SETFL, O_NONBLOCK);

	ep_fd = LTX_EXP_FD(epoll_create1(EPOLL_CLOEXEC));

	ltx_epoll_add(in_fd, EPOLLIN);
	ltx_epoll_add(out_fd, EPOLLOUT | EPOLLET);

	while (!stop) {
		const int eventsn =
			LTX_EXP_POS(epoll_wait(ep_fd, events, maxevents, 100));

		for (int i = 0; i < eventsn; i++) {
			const struct epoll_event *ev = events + i;

			if (ev->events & EPOLLIN)
				fill_read_buf();

			if (ev->events & EPOLLOUT)
				out_fd_blocked = 0;

			if (ev->events & EPOLLHUP)
				stop = 1;
		}

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
