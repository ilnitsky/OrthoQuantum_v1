-- KEYS[1] - enqueued hash f"/tasks/{task_id}/enqueued"
-- KEYS[2] - running hash f"/tasks/{task_id}/running"

-- ARGV[1] = stage name
-- ARGV[2] = q_id


if redis.call('hget', KEYS[1], ARGV[1]) == ARGV[2] then
    redis.call('hset', KEYS[2], ARGV[1], ARGV[2])
    redis.call('hdel', KEYS[1], ARGV[1])
    return 1
elseif redis.call('hget', KEYS[2], ARGV[1]) == ARGV[2] then
    -- job recovery: rerunning previously launched task
    return 2
else
    return 0
end