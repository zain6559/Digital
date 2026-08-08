import re
from dataclasses import dataclass
from .schemas import Risk

@dataclass(frozen=True)
class PolicyAssessment:
    risk: Risk
    requires_confirmation: bool
    reason: str
    intent: str
    action_class: str
    confidence: float

HIGH_ACTIONS = {'delete','remove','wipe','factory reset','purchase','buy','pay','transfer','post','publish','send','message','install','uninstall'}
SENSITIVE = {'account','password','security','settings','apk','money','payment','email','sms','public','device'}
INFO_MARKERS = {'how','what','why','explain','summarize','search','find','remember','note'}
WRITE_TOOLS = {'mobile_input','browser_action','file_write'}

class PolicyGate:
    def _tokens(self, prompt: str) -> set[str]:
        return set(re.findall(r"[a-z0-9_]+", (prompt or '').lower()))

    def analyze(self, prompt: str, tool: str = 'general', context: dict | None = None) -> PolicyAssessment:
        context = context or {}
        tokens = self._tokens(prompt)
        intent = 'informational' if tokens & INFO_MARKERS else 'operate'
        action_class = 'read'
        if tokens & {'tap','click','type','input','open'} or tool in WRITE_TOOLS:
            action_class = 'controlled_external_action'
        if tokens & HIGH_ACTIONS:
            action_class = 'user_visible_or_destructive_action'
        sensitive_hits = sorted(tokens & SENSITIVE)
        dangerous_hits = sorted(tokens & HIGH_ACTIONS)
        confidence = min(0.95, 0.45 + 0.15 * len(dangerous_hits) + 0.08 * len(sensitive_hits))
        if action_class == 'user_visible_or_destructive_action' and (sensitive_hits or context.get('external_effect')):
            return PolicyAssessment(Risk.high, True, f'High-risk {intent} request: {", ".join(dangerous_hits + sensitive_hits)}', intent, action_class, confidence)
        if action_class != 'read':
            return PolicyAssessment(Risk.medium, False, 'Controlled external action; execution is constrained and logged.', intent, action_class, max(confidence, 0.62))
        return PolicyAssessment(Risk.low, False, 'Read-only or memory action with no external side effect detected.', intent, action_class, max(0.55, confidence - 0.2))

    def assess(self, prompt: str, tool: str='general', context: dict | None = None) -> tuple[Risk, bool, str]:
        a = self.analyze(prompt, tool, context)
        return a.risk, a.requires_confirmation, f'{a.reason} intent={a.intent}; action_class={a.action_class}; confidence={a.confidence:.2f}'
policy_gate=PolicyGate()
