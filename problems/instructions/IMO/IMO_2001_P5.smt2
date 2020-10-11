(param (A B C) triangle)

(compute P point (interLL (ibisector B A C) (line B C)))
(compute Q point (interLL (ibisector A B C) (line C A)))

(assert (eq (uangle B A C) (div pi 3)))
(assert (eq (add (dist A B) (dist B P)) (add (dist A Q) (dist Q B))))