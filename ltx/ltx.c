#define _GNU_SOURCE

#include <execinfo.h>
#include <errno.h>
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

__attribute__((nonnull, format(printf, 3, 4)))
static void ltx_fmt(const struct ltx_pos pos,
		    char *const buf,
		    size_t buf_len,
		    const char *const fmt, ...)
{
	va_list vali;

	snprintf(buf, buf_len - 1, "[%s:%s:%i] ", pos.file, pos.func, pos.line);
}

__attribute__((nonnull, format(printf, 2, 3)))
static void ltx_log(const struct ltx_pos pos, const char *const fmt, ...)
{
	va_list vali;

	fprintf(stderr, "[%s:%s:%i] ", pos.file, pos.func, pos.line);

	va_start(vali, fmt);
	vfprintf(stderr, fmt, vali);
	va_end(vali);

	fprintf(stderr, "\n");
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

static const int data_in = STDIN_FILENO;
static const int data_out = STDOUT_FILENO;
static int epfd;

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

			l = LTX_EXP_POS(write(data_out, pong, 2));
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
