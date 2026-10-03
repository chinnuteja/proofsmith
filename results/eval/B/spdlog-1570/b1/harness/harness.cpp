// Reproduction for daily_file_sink deadlock:
// daily_file_sink::sink_it_() runs under base_sink's mutex and calls
// delete_old_() when a rotation happens and max_files > 0. delete_old_()
// calls the public filename(), which tries to acquire the same mutex.
#include <spdlog/common.h>
#include <spdlog/details/log_msg.h>
#include <spdlog/sinks/daily_file_sink.h>

#include <atomic>
#include <chrono>
#include <cstdlib>
#include <string>
#include <thread>
#include <unistd.h>

int main()
{
    char dir_template[] = "/tmp/spdlog_daily_deadlock_XXXXXX";
    char *dir = mkdtemp(dir_template);
    if (dir == nullptr)
    {
        return 2;
    }

    std::string basename = std::string(dir) + "/daily.log";

    // max_files=1 means delete_old_() runs after the first rotation.
    spdlog::sinks::daily_file_sink_mt sink(basename, 0, 0, true, 1);

    spdlog::details::log_msg msg("daily_deadlock_test", spdlog::level::info, "hello");
    msg.time = spdlog::log_clock::now() + std::chrono::hours(24);

    std::atomic<bool> started{false};
    std::atomic<bool> finished{false};

    std::thread worker([&]() {
        started.store(true);
        sink.log(msg);
        finished.store(true);
    });

    while (!started.load())
    {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    // The worker should return in well under a second on a fixed build.
    // On the buggy build it blocks forever trying to re-lock std::mutex.
    for (int i = 0; i < 30; ++i)
    {
        if (finished.load())
        {
            break;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    if (!finished.load())
    {
        // Deadlocked. Exit non-zero without running destructors, since the
        // worker still holds the sink lock.
        _exit(1);
    }

    worker.join();
    return 0;
}
