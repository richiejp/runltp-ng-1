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

#include <sys/types.h>
#include <sys/wait.h>
#include <sys/uio.h>
#include <sys/epoll.h>

#define VERSION "0.0.1-dev"
#define LTX_IOV_MAX 3

#define LTX_POS ((struct ltx_pos){ __FILE__, __func__, __LINE__ })
#define LTX_LOG(fmt, ...) ltx_log(LTX_POS, fmt, ##__VA_ARGS__)

#define assert_expr(expr, fmt, ...) do {				\
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
	char data[BUFSIZ];
};

static const int data_in = STDIN_FILENO;
static const int data_out = STDOUT_FILENO;
static int epfd;

__attribute__((pure, nonnull, warn_unused_result))
static char *ltx_buf_end(struct ltx_buf *const self)
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
	buf->used += snprintf(ltx_buf_end(buf), ltx_buf_avail(buf) - 2,
			      "[%s:%s:%i] ", pos.file, pos.func, pos.line);
	buf->used += vsnprintf(ltx_buf_end(buf), ltx_buf_avail(buf) - 2, fmt, ap);

	memcpy(ltx_buf_end(buf), "\n\0", 2);
	buf->used++;
}

__attribute__((nonnull, warn_unused_result))
static size_t ltx_log_msg(struct iovec *const iov, const struct ltx_buf *const buf)
{
	char *const head = iov[0].iov_base;
	size_t len = 0;

	/* fixarray[3] = { ... */
	head[len++] = 0x93;
	/* msg type = 2 */
	head[len++] = 0x02;
	/* table_id = nil */
	head[len++] = 0xc0;

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

	iov[0].iov_base = head.data;
	iov_len = ltx_log_msg(iov, &msg);
	iov_i = 0;

	while (1) {
		res = writev(data_out, iov + iov_i, iov_len);
		if (res < 0)
			break;

		while ((size_t)res >= iov[iov_i].iov_len) {
			res -= iov[iov_i].iov_len;
			iov_i++;
		}

		if (iov_i == iov_len)
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

__attribute__((nonnull, warn_unused_result))
static int ltx_exp_pos(const struct ltx_pos pos,
		       const int ret,
		       const char *const expr)
{
	if (ret > -1)
		return ret;

	ltx_log(pos, "Not positive: %s = %d: %s", expr, ret, strerrorname_np(errno));

	exit(1);
}

static void ltx_epoll_add(const int fd, const uint32_t events)
{
	struct epoll_event ev = {
		.events = events,
		.data = (epoll_data_t){ .fd = fd },
	};

	LTX_EXP_0(epoll_ctl(epfd, EPOLL_CTL_ADD, fd, &ev));
}

static void event_loop(void)
{
	const char ping[2] = { 0x91, 0x00 };
	char buf[2];
	const int maxevents = 64;
	struct epoll_event events[maxevents];

	epfd = LTX_EXP_FD(epoll_create1(EPOLL_CLOEXEC));

	ltx_epoll_add(data_in, EPOLLIN);

	while (1) {
		const int eventsn = LTX_EXP_POS(epoll_wait(epfd, events, maxevents, 100));

		for (int i = 0; i < eventsn; i++) {
			const struct epoll_event *ev = events + i;
			int l = LTX_EXP_POS(read(data_in, buf, 2));

			assert_expr(l == 2, "read l = %d", l);
			assert_expr(!memcmp(buf, ping, 2), "");

			l = LTX_EXP_POS(write(data_out, ping, 2));
			assert_expr(l == 2, "write l = %d", l);

			if (ev->events | EPOLLHUP)
				return;
		}
	}
}

int main(void)
{
	LTX_LOG("Linux Test Executor " VERSION);

	event_loop();

	return 0;
}
