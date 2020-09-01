def resolve_is_intfar(intfar, intfar_reason, target_id):
    if target_id is None: # Bet was about whether anyone was Int-Far.
        return intfar is not None
    return intfar == target_id # Bet was about a specific person being Int-Far.

def intfar_by_reason(intfar, reason_str, target_id, reason):
    return (resolve_is_intfar(intfar, reason_str, target_id)
            and reason_str[reason] == "1")

intfar = 42
reason_str = "1000"
target_id = 42
reason = 1
print(intfar_by_reason(intfar, reason_str, target_id, reason))
