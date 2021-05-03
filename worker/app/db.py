import redis
db = redis.Redis("redis")

_cas_script = db.register_script("""
    -- CAS: check if the KEYS[1] is equal to ARGV[1], if true
    -- do CAS: set KEYS[2] = KEYS[3] if KEYS[3] is bigger

    local state, cur_val, new_val = unpack(redis.call('MGET', KEYS[1], KEYS[2], KEYS[3]))

    cur_val = tonumber(cur_val)
    new_val = tonumber(new_val)

    if (state ~= ARGV[1]) then
        return cur_val
    end

    if (cur_val == nil or cur_val<new_val) then
        redis.call('SET', KEYS[2], new_val)
        return new_val
    else
        return cur_val
    end
""")

def queueinfo_upd(task_id:str, client=None) -> int:
    return _cas_script(
        keys=(
            f"/tasks/{task_id}/stage/table/status",
            "/queueinfo/last_launched_id",
            f"/tasks/{task_id}/stage/table/current",
        ),
        args=("Enqueued",),
        client=client,
    )
