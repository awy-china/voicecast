"""音色溯源：'这声音哪来的'可追溯，输出元数据同步携带。"""

from __future__ import annotations

from ..core.models import DesignMethod, VoiceProfile


def provenance_check(profile: VoiceProfile) -> list[str]:
    """返回违规/缺失项列表（空 = 合规）。"""
    issues: list[str] = []
    p = profile.provenance
    if profile.design == DesignMethod.CLONE:
        if not p.authorized:
            issues.append("克隆音色未声明授权（违反克隆门禁）")
        if not p.ref_file:
            issues.append("克隆音色缺少参考音频记录 ref_file")
    if profile.design == DesignMethod.MIX:
        if not p.authorized:
            issues.append("混合音色未声明参考素材授权")
    if not p.note:
        issues.append("缺少来源说明 note（建议补充）")
    return issues


def provenance_meta(profile: VoiceProfile) -> dict:
    """输出元数据携带的溯源字段。"""
    return {
        "voice_id": profile.id,
        "origin": profile.provenance.origin,
        "authorized": profile.provenance.authorized,
        "ref_file": profile.provenance.ref_file,
        "note": profile.provenance.note,
    }
