SELECT p1.disc_id, p2.disc_id, Count(*) as c FROM participants p1, participants p2
WHERE p1.disc_id != p2.disc_id AND p1.game_id = p2.game_id AND p1.disc_id=172757468814770176
GROUP BY p1.disc_id, p2.disc_id
ORDER BY c DESC