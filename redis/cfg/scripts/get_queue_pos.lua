-- KEYS[1] - queue_key

-- ARGV[1] - worker_group_name  //worker_group
-- ARGV[2] - current (used as element id source) "1622079118529-0"

-- returns: >0 if there are items in front of the current
-- 0 if already working
-- -1 on error

local info = redis.call('XINFO', 'GROUPS', KEYS[1])
local last_id = '-'
local found_name = false
for i = 1, #info do
    last_id = '-'
    found_name = false
    for j = 1, #info[i], 2 do
        if (info[i][j] == 'name') then
            if (info[i][j+1] == ARGV[1]) then
                found_name = true
                if (last_id ~= '-') then
                    break
                end
            else
                break
            end
        elseif (info[i][j] == 'last-delivered-id') then
            last_id = info[i][j+1]
            if (found_name) then
                break
            end
        end
    end
    if (found_name) then
        break
    end
end
if (not found_name) then
    return -1
end

local res = #redis.call('XRANGE', KEYS[1], last_id, ARGV[2])
if (res == 0) then
    return 0
else
    return res - 1
end
