-- append string to hash key
-- KEYS[1] - hash
-- ARGV[1] - hash key
-- ARGV[2] - string_to_append
-- ARGV[3] - separator (optional)

local curVal = redis.call('hget', KEYS[1], ARGV[1])
if curVal == false then
    curVal = ''
end

-- separator provided and current value is not empty
if (#ARGV == 3) and (curVal ~= '') then
    redis.call('hset', KEYS[1], ARGV[1], curVal .. ARGV[3] .. ARGV[2])
else
    redis.call('hset', KEYS[1], ARGV[1], curVal .. ARGV[2])
end

