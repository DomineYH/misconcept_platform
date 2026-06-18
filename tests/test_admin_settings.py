"""Admin settings page — synthesis on/off toggle (Issue #55)."""

from src.services.app_settings import is_synthesis_enabled


def _checkbox_markup(html: str) -> str:
    """페이지 본문에서 체크박스 <input ...> 요소 부분만 추출한다.

    JS 코드 안의 `checkbox.checked` 같은 부분 문자열이 단순 `"checked"
    in html` 검사를 우발적으로 통과하지 않도록 마크업만 검사한다.
    """
    needle = 'id="synthesis-enabled-checkbox"'
    idx = html.find(needle)
    if idx == -1:
        return ""
    start = html.rfind("<input", 0, idx)
    end = html.find(">", idx)
    return html[start : end + 1] if start != -1 and end != -1 else ""


async def test_admin_get_settings_page(admin_async_client):
    """관리자는 /admin/settings 를 200으로 조회할 수 있다."""
    response = await admin_async_client.get("/admin/settings")
    assert response.status_code == 200
    body = response.text
    assert "분석 설정" in body
    assert "대화 서술형 분석" in body
    # 기본값 ON 반영: 체크박스가 checked 상태
    assert "checked" in _checkbox_markup(body)


async def test_non_admin_blocked_from_settings(
    authenticated_async_client,
):
    """일반 교사 계정은 /admin/settings 에 접근할 수 없다."""
    response = await authenticated_async_client.get("/admin/settings")
    assert response.status_code == 403


async def test_admin_post_turns_synthesis_off_then_on(
    admin_async_client, async_db_session
):
    """POST 토글이 DB에 반영되고 GET 조회에도 반영된다."""
    # OFF 로 전환
    response = await admin_async_client.post(
        "/admin/settings/synthesis",
        data={"synthesis_enabled": "false"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "분석 설정" in response.text

    enabled = await is_synthesis_enabled(async_db_session)
    assert enabled is False

    # GET 조회에서도 OFF 상태를 반영(체크박스 미체크)
    get_resp = await admin_async_client.get("/admin/settings")
    assert get_resp.status_code == 200
    assert 'id="synthesis-enabled-checkbox"' in get_resp.text
    assert "checked" not in _checkbox_markup(get_resp.text)

    # 다시 ON 으로 전환
    await admin_async_client.post(
        "/admin/settings/synthesis",
        data={"synthesis_enabled": "true"},
        follow_redirects=True,
    )
    enabled_after = await is_synthesis_enabled(async_db_session)
    assert enabled_after is True


async def test_non_admin_blocked_from_post(
    authenticated_async_client,
):
    """일반 교사 계정은 POST 토글도 금지된다."""
    response = await authenticated_async_client.post(
        "/admin/settings/synthesis",
        data={"synthesis_enabled": "false"},
    )
    assert response.status_code == 403
