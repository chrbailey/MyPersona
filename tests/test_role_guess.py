import pytest
from app.services.role_guess import _parse_role_response
from app.models import RoleType


class TestRoleProbabilitySum:
    """Test that role probabilities sum to 1 per spec section 4.3."""

    def test_probabilities_sum_to_one_exact(self):
        """Exact probabilities should sum to 1."""
        response = """
role_guess:
  roles:
    professional: 0.72
    personal: 0.21
    casual: 0.07
  primary_role: professional
  confidence: 0.72
"""
        role_guess = _parse_role_response(response)
        total = (
            role_guess.roles.professional +
            role_guess.roles.personal +
            role_guess.roles.casual
        )
        assert abs(total - 1.0) < 0.01  # Allow small rounding error

    def test_probabilities_normalized(self):
        """Non-normalized probabilities should be normalized to sum to 1."""
        response = """
roles:
  professional: 0.5
  personal: 0.3
  casual: 0.3
primary_role: professional
confidence: 0.5
"""
        role_guess = _parse_role_response(response)
        total = (
            role_guess.roles.professional +
            role_guess.roles.personal +
            role_guess.roles.casual
        )
        assert abs(total - 1.0) < 0.01

    def test_all_three_roles_present(self):
        """All three roles must be present in response."""
        response = """
roles:
  professional: 0.7
  personal: 0.2
  casual: 0.1
primary_role: professional
confidence: 0.7
"""
        role_guess = _parse_role_response(response)

        assert role_guess.roles.professional is not None
        assert role_guess.roles.personal is not None
        assert role_guess.roles.casual is not None

    def test_handles_missing_roles_gracefully(self):
        """Missing roles should get default values."""
        response = """
roles:
  professional: 1.0
primary_role: professional
confidence: 0.5
"""
        role_guess = _parse_role_response(response)
        # Should still work with defaults
        assert role_guess is not None
        total = (
            role_guess.roles.professional +
            role_guess.roles.personal +
            role_guess.roles.casual
        )
        assert abs(total - 1.0) < 0.01

    def test_handles_code_block_wrapper(self):
        """Should handle markdown code blocks in response."""
        response = """```yaml
roles:
  professional: 0.6
  personal: 0.3
  casual: 0.1
primary_role: professional
confidence: 0.6
```"""
        role_guess = _parse_role_response(response)
        assert role_guess.primary_role == RoleType.PROFESSIONAL

    def test_confidence_in_range(self):
        """Confidence should be between 0 and 1."""
        response = """
roles:
  professional: 0.6
  personal: 0.3
  casual: 0.1
primary_role: professional
confidence: 0.6
"""
        role_guess = _parse_role_response(response)
        assert 0.0 <= role_guess.confidence <= 1.0
