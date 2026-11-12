from app.domain.scoring import points_for


def test_bonus_in_first_half():
    assert points_for(0, 20) == 15
    assert points_for(9.9, 20) == 15


def test_base_points_in_second_half():
    assert points_for(10.1, 20) == 10
    assert points_for(20, 20) == 10


def test_no_points_after_limit():
    assert points_for(20.01, 20) == 0


def test_custom_values():
    assert points_for(1, 10, base=5, bonus=2) == 7
    assert points_for(8, 10, base=5, bonus=2) == 5
