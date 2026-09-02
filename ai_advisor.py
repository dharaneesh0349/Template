"""
AI Advisor & Self-Healing Module for CloudStack Template Automation.
Analyzes execution errors, package repository issues, and hypervisor mismatches
using OpenAI / Anthropic APIs, or deterministic expert rule fallback.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("ai_advisor")

class AIAdvisor:
    def __init__(self, api_key: Optional[str] = None, provider: str = "auto"):
        self.openai_key = api_key or os.getenv("OPENAI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.provider = provider

    def diagnose_error(self, step_name: str, command: str, error_output: str, environment: Dict[str, Any]) -> Dict[str, Any]:
        """
        Diagnose an execution step failure and return remediation recommendations.
        """
        distro = environment.get("distribution", "linux")
        version = environment.get("version", "")
        pkg_mgr = environment.get("package_manager", "")

        # Try LLM diagnosis if API key is present
        if self.openai_key and self.provider in ["auto", "openai"]:
            try:
                return self._diagnose_with_openai(step_name, command, error_output, environment)
            except Exception as e:
                logger.warning(f"OpenAI diagnosis failed, falling back to rule engine: {e}")

        if self.anthropic_key and self.provider in ["auto", "anthropic"]:
            try:
                return self._diagnose_with_anthropic(step_name, command, error_output, environment)
            except Exception as e:
                logger.warning(f"Anthropic diagnosis failed, falling back to rule engine: {e}")

        # Deterministic Expert Rule Engine Fallback
        return self._rule_based_diagnosis(step_name, command, error_output, distro, version, pkg_mgr)

    def _rule_based_diagnosis(self, step: str, command: str, error: str, distro: str, version: str, pkg_mgr: str) -> Dict[str, Any]:
        err_lower = error.lower()

        # Rule 1: EPEL repository required on CentOS / RHEL
        if "no package cloud-init available" in err_lower or "unable to find a match: cloud-init" in err_lower:
            if "centos" in str(distro).lower() or "rhel" in str(distro).lower() or "yum" in command.lower() or "dnf" in command.lower():
                return {
                    "root_cause": "The cloud-init package is not in the base repository. EPEL repository must be enabled.",
                    "severity": "high",
                    "can_auto_recover": True,
                    "remediation_commands": [
                        "yum install -y epel-release || dnf install -y epel-release",
                        "yum makecache || dnf makecache",
                        f"{pkg_mgr or 'yum'} install -y cloud-init"
                    ],
                    "advice": "Enable EPEL repository and refresh package metadata."
                }

        # Rule 2: Apt lock issue on Ubuntu / Debian
        if "could not get lock" in err_lower or "is another process using it" in err_lower:
            return {
                "root_cause": "Apt package manager is locked by background unattended-upgrades or another apt process.",
                "severity": "medium",
                "can_auto_recover": True,
                "remediation_commands": [
                    "killall apt apt-get unattended-upgr 2>/dev/null || true",
                    "rm -f /var/lib/apt/lists/lock /var/cache/apt/archives/lock /var/lib/dpkg/lock*",
                    "dpkg --configure -a",
                    command
                ],
                "advice": "Wait for background automatic update to complete or release stale apt locks."
            }

        # Rule 3: SSH Key generation or permission error
        if "permission denied" in err_lower:
            return {
                "root_cause": "Insufficient permissions to execute command or modify system files.",
                "severity": "high",
                "can_auto_recover": False,
                "remediation_commands": [
                    f"sudo {command}"
                ],
                "advice": "Ensure the SSH user has root or full passwordless sudo privileges."
            }

        # Rule 4: Guest agent package missing in specific minimal distros
        if "guest-agent" in command.lower() and ("not found" in err_lower or "no match" in err_lower):
            return {
                "root_cause": "Hypervisor guest agent package is optional and not present in default repositories.",
                "severity": "low",
                "can_auto_recover": True,
                "remediation_commands": [],
                "advice": "Guest agent installation is non-critical for basic cloud-init template functionality. You may safely skip this step."
            }

        # Default fallback
        return {
            "root_cause": "Command execution failed with standard error.",
            "severity": "medium",
            "can_auto_recover": False,
            "remediation_commands": [
                "journalctl -xe --no-pager | tail -n 30",
                "dmesg | tail -n 20"
            ],
            "advice": f"Review target VM system logs for details on '{step}'."
        }

    def _diagnose_with_openai(self, step: str, command: str, error: str, env: Dict[str, Any]) -> Dict[str, Any]:
        from openai import OpenAI
        client = OpenAI(api_key=self.openai_key)

        prompt = f"""
You are an expert Linux and CloudStack engineer.
Analyze this failed template automation step:
- Step Name: {step}
- Target Environment: {json.dumps(env, default=str)}
- Executed Command: {command}
- Error Output: {error}

Respond in STRICT JSON format matching this schema:
{{
  "root_cause": "brief explanation",
  "severity": "low" | "medium" | "high",
  "can_auto_recover": true | false,
  "remediation_commands": ["command1", "command2"],
  "advice": "practical suggestions for the operator"
}}
"""
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You are a Linux CloudStack template automation diagnostics system. Always output valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)

    def _diagnose_with_anthropic(self, step: str, command: str, error: str, env: Dict[str, Any]) -> Dict[str, Any]:
        import anthropic
        client = anthropic.Anthropic(api_key=self.anthropic_key)

        prompt = f"""
You are an expert Linux and CloudStack engineer.
Analyze this failed template automation step:
- Step Name: {step}
- Target Environment: {json.dumps(env, default=str)}
- Executed Command: {command}
- Error Output: {error}

Respond ONLY with valid JSON with keys: root_cause, severity (low/medium/high), can_auto_recover (boolean), remediation_commands (array of strings), advice (string).
"""
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.content[0].text
        # extract json if fenced
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        return json.loads(content)
