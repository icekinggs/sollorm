from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import AsyncSessionLocal, get_db
from app.models import Agent, AlertEvent, AlertRule, User
from app.schemas import AlertEventOut, AlertRuleCreate, AlertRuleOut, AlertRuleUpdate

router = APIRouter(tags=["alerts"])

METRIC_LABELS = {
    "cpu_usage_percent": "CPU",
    "ram_usage_percent": "RAM",
    "disk_usage_percent": "Disco",
}


def _event_out(event: AlertEvent) -> AlertEventOut:
    return AlertEventOut(
        id=event.id,
        rule_id=event.rule_id,
        rule_name=event.rule.name if event.rule else None,
        agent_id=event.agent_id,
        agent_hostname=event.agent.hostname if event.agent else None,
        metric=event.metric,
        value=event.value,
        threshold=event.threshold,
        operator=event.operator,
        severity=event.severity,
        state=event.state,
        fired_at=event.fired_at,
        resolved_at=event.resolved_at,
    )


# ── CRUD rules ──────────────────────────────────────────────────────────────

@router.get("/alert-rules", response_model=list[AlertRuleOut])
async def list_alert_rules(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AlertRule).order_by(AlertRule.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/alert-rules", response_model=AlertRuleOut, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    payload: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.agent_id is not None:
        res = await db.execute(select(Agent).where(Agent.id == payload.agent_id))
        if res.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Agente não encontrado")

    rule = AlertRule(
        name=payload.name,
        agent_id=payload.agent_id,
        metric=payload.metric,
        operator=payload.operator,
        threshold=payload.threshold,
        severity=payload.severity,
        created_by_user_id=current_user.id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.put("/alert-rules/{rule_id}", response_model=AlertRuleOut)
async def update_alert_rule(
    rule_id: str,
    payload: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Regra não encontrada")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(rule, field, value)

    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/alert-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    await db.delete(rule)
    await db.commit()


# ── Alert events ─────────────────────────────────────────────────────────────

@router.get("/alerts", response_model=list[AlertEventOut])
async def list_alert_events(
    state: str | None = Query(None),   # firing | resolved | None=all
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from sqlalchemy.orm import selectinload
    query = (
        select(AlertEvent)
        .options(selectinload(AlertEvent.rule), selectinload(AlertEvent.agent))
        .order_by(AlertEvent.fired_at.desc())
        .limit(limit)
    )
    if state:
        query = query.where(AlertEvent.state == state)
    result = await db.execute(query)
    return [_event_out(e) for e in result.scalars().all()]


@router.get("/agents/{agent_id}/alerts", response_model=list[AlertEventOut])
async def list_agent_alert_events(
    agent_id: str,
    state: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from sqlalchemy.orm import selectinload
    query = (
        select(AlertEvent)
        .options(selectinload(AlertEvent.rule), selectinload(AlertEvent.agent))
        .where(AlertEvent.agent_id == agent_id)
        .order_by(AlertEvent.fired_at.desc())
        .limit(limit)
    )
    if state:
        query = query.where(AlertEvent.state == state)
    result = await db.execute(query)
    return [_event_out(e) for e in result.scalars().all()]


# ── Evaluation engine ─────────────────────────────────────────────────────────

def _check(value: float, operator: str, threshold: float) -> bool:
    if operator == ">":   return value > threshold
    if operator == ">=":  return value >= threshold
    if operator == "<":   return value < threshold
    if operator == "<=":  return value <= threshold
    return False


async def evaluate_alert_rules(agent_id: str, metrics: dict) -> None:
    from app.routers.notifications import broadcast  # lazy
    from sqlalchemy.orm import selectinload

    async with AsyncSessionLocal() as db:
        rules_result = await db.execute(
            select(AlertRule)
            .where(AlertRule.enabled == True)
            .where(or_(AlertRule.agent_id == agent_id, AlertRule.agent_id.is_(None)))
        )
        rules = rules_result.scalars().all()

        now = datetime.now(timezone.utc)

        for rule in rules:
            value = metrics.get(rule.metric)
            if value is None:
                continue

            violated = _check(value, rule.operator, rule.threshold)

            active_result = await db.execute(
                select(AlertEvent)
                .where(AlertEvent.rule_id == rule.id)
                .where(AlertEvent.agent_id == agent_id)
                .where(AlertEvent.state == "firing")
            )
            active = active_result.scalar_one_or_none()

            if violated and active is None:
                event = AlertEvent(
                    rule_id=rule.id,
                    agent_id=agent_id,
                    metric=rule.metric,
                    value=value,
                    threshold=rule.threshold,
                    operator=rule.operator,
                    severity=rule.severity,
                    state="firing",
                    fired_at=now,
                )
                db.add(event)
                await db.flush()
                await broadcast({
                    "type": "alert_fired",
                    "event_id": event.id,
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "agent_id": agent_id,
                    "metric": rule.metric,
                    "value": value,
                    "threshold": rule.threshold,
                    "operator": rule.operator,
                    "severity": rule.severity,
                    "fired_at": now.isoformat(),
                })

            elif not violated and active is not None:
                active.state = "resolved"
                active.resolved_at = now
                await broadcast({
                    "type": "alert_resolved",
                    "event_id": active.id,
                    "rule_id": rule.id,
                    "agent_id": agent_id,
                    "metric": rule.metric,
                    "severity": rule.severity,
                    "resolved_at": now.isoformat(),
                })

        await db.commit()
