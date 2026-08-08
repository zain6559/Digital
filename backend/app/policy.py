from .schemas import Risk

DANGEROUS_TERMS={'delete','purchase','post','send message','factory reset','install apk','uninstall','password','security settings'}
class PolicyGate:
    def assess(self, prompt: str, tool: str='general') -> tuple[Risk, bool, str]:
        text=prompt.lower()
        if any(t in text for t in DANGEROUS_TERMS): return Risk.high, True, 'High-risk user-visible action requires confirmation.'
        if tool in {'mobile_input','browser_action','file_write'}: return Risk.medium, False, 'Medium-risk controlled action.'
        return Risk.low, False, 'Low-risk action permitted.'
policy_gate=PolicyGate()
