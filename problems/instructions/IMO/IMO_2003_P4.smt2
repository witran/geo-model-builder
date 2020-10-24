(param (A B C D) polygon)
(assert (cycl A B C D))
(compute P point (foot D (line A B)))
(compute Q point (foot D (line B C)))
(compute R point (foot D (line C A)))
(assert (cong R P R Q))
(eval (concur (i-bisector A B C) (i-bisector C D A) (line A C)))