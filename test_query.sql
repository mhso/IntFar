SELECT MAX(pcts.pct), pcts.intboi FROM 
(
    SELECT (intfar_counts.c / games_counts.c) * 100 AS pct, intfar_counts.int_far AS intboi FROM
    (
        SELECT int_far, CAST(Count(*) as real) as c FROM best_stats
        WHERE int_far IS NOT NULL GROUP BY int_far
    ) AS intfar_counts,
    (
        SELECT disc_id, CAST(Count(*) as real) as c FROM participants
        GROUP BY disc_id
    ) AS games_counts
    WHERE int_far=disc_id AND games_counts.c > 10
) AS pcts;