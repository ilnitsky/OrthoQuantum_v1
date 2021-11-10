-- get script
-- KEYS[1] - version key
-- KEYS[2] - zset version-component
-- KEYS[3] - zset version-component for particular connection (client-issued updates)
-- KEYS[4] - scratch zset
-- KEYS[5] - hash with data

-- ARGV[1] - last known version + 1 (first version in which client is interested)

-- extract all new updates into scratch zset
redis.call('ZRANGESTORE', KEYS[4], KEYS[2], ARGV[1], '+inf', 'BYSCORE')
-- Subtract client update versions from all new updates
-- Client update versions <= global versions.
-- Subtraction result = 0 means that client already has the state
-- since they are responsible for creating the update in the first place
redis.call('ZUNIONSTORE', KEYS[4], 2, KEYS[4], KEYS[3], 'WEIGHTS', 1, -1, 'AGGREGATE', 'SUM')
local updatedKeys = redis.call('ZRANGE', KEYS[4], 1, '+inf', 'BYSCORE')

local updatedData
if next(updatedKeys) ~= nil then
    updatedData = redis.call('hmget', KEYS[5], unpack(updatedKeys))
else
    updatedData = {}
end
return {redis.call('get', KEYS[1]), updatedKeys, updatedData}
