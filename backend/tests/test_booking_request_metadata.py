from src.api.routes_booking_requests import _seat_change_metadata


def test_seat_change_metadata_uses_segment_boundary_station():
    topology = {
        "stations": [
            {"id": "HNO"}, {"id": "PHD"}, {"id": "NBI"},
            {"id": "THO"}, {"id": "BSO"}, {"id": "VIN"}, {"id": "YEN"},
        ]
    }
    seat_plan = [
        {
            "seat_id": "NGOI_MEM_DH:0000", "segment_from": 4,
            "segment_to": 4, "requires_seat_change": True,
        },
        {
            "seat_id": "NGOI_MEM_DH:0001", "segment_from": 5,
            "segment_to": 6, "requires_seat_change": True,
        },
    ]

    assert _seat_change_metadata(seat_plan, topology) == (["BSO"], 1)


def test_seat_change_metadata_ignores_single_seat_plan():
    topology = {"stations": [{"id": "HNO"}, {"id": "PHD"}]}
    seat_plan = [{
        "seat_id": "NGOI_MEM_DH:0000", "segment_from": 1,
        "segment_to": 1, "requires_seat_change": False,
    }]

    assert _seat_change_metadata(seat_plan, topology) == ([], 0)
