-- get script
-- KEYS[1] - version key
-- KEYS[2] - zset version-component
-- KEYS[3] - hash with data
-- KEYS[4] - zset version-component for particular connection (client-issued updates) [optional]
-- KEYS[5] - scratch zset required if KEY[4] is given

-- ARGV[1] - last known version + 1 (first version in which client is interested)

-- extract all new updates into scratch zset
local updatedKeys
if KEYS[4] ~= nil then
    redis.call('ZRANGESTORE', KEYS[5], KEYS[2], ARGV[1], '+inf', 'BYSCORE')
    -- Subtract client update versions from all new updates
    -- Client update versions <= global versions.
    -- Subtraction result = 0 means that client already has the state
    -- since they are responsible for creating the update in the first place
    redis.call('ZUNIONSTORE', KEYS[5], 2, KEYS[5], KEYS[4], 'WEIGHTS', 1, -1, 'AGGREGATE', 'SUM')
    updatedKeys = redis.call('ZRANGE', KEYS[5], 1, '+inf', 'BYSCORE')
else
    updatedKeys = redis.call('ZRANGE', KEYS[2], ARGV[1], '+inf', 'BYSCORE')
end

local updatedData
if next(updatedKeys) ~= nil then
    updatedData = redis.call('hmget', KEYS[3], unpack(updatedKeys))
else
    updatedData = {}
end
return {redis.call('GET', KEYS[1]), updatedKeys, updatedData}
