from dataclasses import dataclass


@dataclass
class Booking:
    id: int
    user_id: int
    service: str
    date: str
    time: str
    full_name: str
    username: str
    phone: str
