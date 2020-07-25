SELECT Count(*) as c, disc_id FROM best_stats bs, participants p 
WHERE bs.game_id=p.game_id
AND timestamp > 1594302805 AND timestamp < 1595685288 
GROUP BY disc_id ORDER BY c;
