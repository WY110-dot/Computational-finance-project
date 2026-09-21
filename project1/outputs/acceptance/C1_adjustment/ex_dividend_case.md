# Ex-Dividend Case

Verified by `test_dividend_event_does_not_create_false_loss` in `tests/test_adjustment.py`.
The raw price drops mechanicallly, but the adjustment factor offsets this, keeping `ret_total` consistent with the economic reality.
