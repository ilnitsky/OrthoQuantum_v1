-- KEYS[1] - queue key f"/queues/{stage}"
-- KEYS[2] - enqueued hash f"/tasks/{task_id}/enqueued"
-- KEYS[3] - running hash f"/tasks/{task_id}/running"
-- KEYS[4] - cancelled jobs channel "/canceled_jobs"

-- ARGV - kv pairs to add to the queue (leave empty to only cancel)
-- ARGV[-1] = stage name

local stage = table.remove(ARGV)
local new_queue_id = ''

local old_qids = {
    redis.call('hget', KEYS[2], stage),
    redis.call('hget', KEYS[3], stage)
}

if #ARGV ~= 0 then
    -- enqueue
    new_queue_id = redis.call('xadd', KEYS[1], '*', unpack(ARGV))
    redis.call('hset', KEYS[2], stage, new_queue_id)
else
    redis.call('hdel', KEYS[2], stage)
end

redis.call('hdel', KEYS[3], stage)

for i=1, #old_qids do
    if old_qids[i] then
        -- cleanup
        redis.call('xdel', KEYS[1], old_qids[i])
        redis.call('publish', KEYS[4], KEYS[1] .. ":" .. old_qids[i])
    end
end

return new_queue_id
