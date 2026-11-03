from datetime import date, timedelta

import pytest

from database.db import SessionLocal
from database.models import BannerMessage, UserRole
from services.banner_service import BannerService

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)


def add_banner(title, family_id, start=TODAY, end=TOMORROW, active=True):
    db = SessionLocal()
    try:
        banner = BannerMessage(
            title=title,
            message="Message",
            family_id=family_id,
            start_date=start,
            end_date=end,
            active=active,
        )
        db.add(banner)
        db.commit()
        return banner.id
    finally:
        db.close()


def get_saved(banner_id):
    db = SessionLocal()
    try:
        return db.get(BannerMessage, banner_id)
    finally:
        db.close()


def titles(banners):
    return {banner.title for banner in banners}


def new_banner():
    return BannerService.create_banner("New", "Message", TODAY, TOMORROW)


def rename(banner_id):
    return BannerService.update_banner(
        banner_id, "Renamed", "Message", TODAY, TOMORROW
    )


@pytest.fixture
def banners(world):
    return dict(
        smith=add_banner("Smith", world.smith),
        jones=add_banner("Jones", world.jones),
        system=add_banner("System", None),
    )


@pytest.fixture
def as_admin(world, login):
    login(None, UserRole.ADMIN)
    return world


# ----- What people see on their dashboards -----


def test_parent_sees_own_family_and_system_banners(smith_parent, banners):
    assert titles(BannerService.get_active_banners()) == {"Smith", "System"}


def test_student_sees_own_family_and_system_banners(world, login, banners):
    login(world.smith, UserRole.STUDENT, world.ann)

    assert titles(BannerService.get_active_banners()) == {"Smith", "System"}


def test_dashboards_hide_archived_and_out_of_date_banners(smith_parent):
    w = smith_parent
    add_banner("Archived", w.smith, active=False)
    add_banner("Archived system", None, active=False)
    add_banner("Ended", w.smith, TODAY - timedelta(days=2), TODAY - timedelta(days=1))
    add_banner("Future", w.smith, TOMORROW, TOMORROW)
    add_banner("Live", w.smith)

    assert titles(BannerService.get_active_banners()) == {"Live"}


# ----- What a parent can manage -----


def test_parent_manages_only_own_family_banners(smith_parent, banners):
    assert titles(BannerService.get_manageable_banners()) == {"Smith"}


def test_manage_list_hides_archived(smith_parent):
    add_banner("Archived", smith_parent.smith, active=False)

    assert BannerService.get_manageable_banners() == []


def test_parent_creates_family_banner(smith_parent):
    assert get_saved(new_banner().id).family_id == smith_parent.smith


def test_parent_can_edit_and_archive_own_banner(smith_parent, banners):
    assert rename(banners["smith"])
    assert get_saved(banners["smith"]).title == "Renamed"

    assert BannerService.archive_banner(banners["smith"])
    assert get_saved(banners["smith"]).active is False


@pytest.mark.parametrize("target", ["jones", "system"])
def test_parent_cannot_touch_other_banners(smith_parent, banners, target):
    banner_id = banners[target]
    title = get_saved(banner_id).title

    assert BannerService.get_banner_by_id(banner_id) is None
    assert rename(banner_id) is None
    assert BannerService.archive_banner(banner_id) is None

    saved = get_saved(banner_id)
    assert saved.title == title
    assert saved.active is True


# ----- What an Admin can manage -----


def test_admin_manages_only_system_banners(as_admin, banners):
    assert titles(BannerService.get_manageable_banners()) == {"System"}


def test_admin_creates_system_banner(as_admin):
    assert get_saved(new_banner().id).family_id is None


def test_admin_can_edit_and_archive_system_banner(as_admin, banners):
    assert rename(banners["system"])
    assert BannerService.archive_banner(banners["system"])
    assert get_saved(banners["system"]).active is False


def test_admin_cannot_touch_family_banners(as_admin, banners):
    assert BannerService.get_banner_by_id(banners["smith"]) is None
    assert rename(banners["smith"]) is None
    assert BannerService.archive_banner(banners["smith"]) is None
    assert get_saved(banners["smith"]).active is True


def test_system_banner_reaches_every_family(as_admin, login, banners):
    created = new_banner()

    login(as_admin.jones)

    assert created.title in titles(BannerService.get_active_banners())


# ----- People who can't manage anything -----


def test_student_cannot_manage_banners(world, login, banners):
    login(world.smith, UserRole.STUDENT, world.ann)

    assert BannerService.get_manageable_banners() == []
    assert new_banner() is None
    assert rename(banners["smith"]) is None
    assert BannerService.archive_banner(banners["smith"]) is None


def test_parent_without_family_cannot_reach_system_banners(world, login, banners):
    login(None, UserRole.PARENT)

    assert BannerService.get_manageable_banners() == []
    assert new_banner() is None
    assert rename(banners["system"]) is None
    assert BannerService.archive_banner(banners["system"]) is None
