-- KEYS[1] - queue key f"/queues/{stage}"
-- KEYS[2] - enqueued hash f"/tasks/{task_id}/enqueued"
-- KEYS[3] - running hash f"/tasks/{task_id}/running"
-- KEYS[4] - cancelled jobs channel "/canceled_jobs"

-- ARGV - kv pairs to add to the queue (leave empty to only cancel)
-- ARGV[-2] = work group name
-- ARGV[-1] = stage name

local stage = table.remove(ARGV)
local group = table.remove(ARGV)
local new_queue_id = ''

local old_enqueued = redis.call('hget', KEYS[2], stage)
local old_running = redis.call('hget', KEYS[3], stage)

if #ARGV ~= 0 then
    -- enqueue
    new_queue_id = redis.call('xadd', KEYS[1], '*', unpack(ARGV))
    redis.call('hset', KEYS[2], stage, new_queue_id)  -- add to enqueued
else
    -- cancel
    if old_enqueued then
        redis.call('hdel', KEYS[2], stage)
    end
end

if old_enqueued then
    -- cleanup queue: task wasn't launched
    -- attempt to prevend delivery of the task to the worker
    -- if worker already took the task - it would fail to launch
    -- since the enqueued id for this stage no longer matches the task id
    redis.call('xdel', KEYS[1], old_enqueued)
    redis.call('xack', KEYS[1], group, old_enqueued)
end

if old_running then
    -- results in running task cancellation
    -- note: the only place where we update the "/tasks/{task_id}/running"
    -- are "launch" and "finish" scripts.
    -- This means that untill some new task calls "launch" the current task is
    -- allowed to update the database. It would be in cancelled state from the asyncio
    -- angle, but the DbClient would continue to perform adequatly

    -- This way we can finish critical sections and clean up progress bars before calling
    -- "finish" and locking ourselves out of the db for good

    redis.call('publish', KEYS[4], KEYS[1] .. ":" .. old_running)
end

return new_queue_id
