-- update script
-- KEYS[1] - version key
-- KEYS[2] - zset key
-- KEYS[3] - zset version-component for particular connection (client updates) [optional]
-- ARGV - items to update

local version = redis.call('incr', KEYS[1])
local items = {}
for i=1,#ARGV do
    table.insert(items, version)
    table.insert(items, ARGV[i])
end
redis.call('zadd', KEYS[2], unpack(items))
if KEYS[3] ~= nil then
    redis.call('zadd', KEYS[3], unpack(items))

    -- after a 5 minutes of inactivity assume the session is over and cleanup
    -- this is non-critical, worst case:
    -- client may receive their own data back at them as if the server has changed it
    -- in a very specific case of client sending update, but not checking for updates from server
    -- for 5 minutes after that
    redis.call('EXPIRE', KEYS[3], 300)
end
return version