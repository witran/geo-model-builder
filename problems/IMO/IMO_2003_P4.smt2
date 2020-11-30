(param (A B C D) polygon)
(assert (cycl A B C D))
(define P point (foot D (line A B)))
(define Q point (foot D (line B C)))
(define R point (foot D (line C A)))
(assert (cong R P R Q))
(eval (concur (i-bisector A B C) (i-bisector C D A) (line A C)))