-- get script
-- KEYS[1] - version key
-- KEYS[2] - zset version-component
-- KEYS[3] - hash with data
-- KEYS[4] - connection counter

local updatedKeys = redis.call('ZRANGE', KEYS[2], 1, '+inf', 'BYSCORE')
local updatedData
if next(updatedKeys) ~= nil then
    updatedData = redis.call('HMGET', KEYS[3], unpack(updatedKeys))
else
    updatedData = {}
end
return {redis.call('GET', KEYS[1]) or 0, redis.call('INCR', KEYS[4]), updatedKeys, updatedData}
