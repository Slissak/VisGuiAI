"""Calculates the cost of LLM requests based on token usage and pricing data."""

from src.shared.config.config_loader import get_config_loader
from src.utils.logging import get_logger

logger = get_logger(__name__)


class CostCalculator:
    """Calculates the cost of LLM requests based on token usage and pricing data."""

    def __init__(self):
        config_loader = get_config_loader()
        self.pricing_data = config_loader.get_pricing_data()
        logger.info(f"CostCalculator initialized with {len(self.pricing_data)} models")

    def calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate the cost of a request given the model and token counts.

        Args:
            model: Model name (e.g., "claude-3-sonnet", "gpt-4")
            prompt_tokens: Number of input/prompt tokens
            completion_tokens: Number of output/completion tokens

        Returns:
            Cost in USD
        """
        if model not in self.pricing_data:
            logger.warning(f"Model '{model}' not found in pricing data. Returning $0.00")
            return 0.0

        pricing = self.pricing_data[model]
        input_cost = (prompt_tokens / 1000) * pricing.get('input_cost_per_1k_tokens', 0.0)
        output_cost = (completion_tokens / 1000) * pricing.get('output_cost_per_1k_tokens', 0.0)

        total_cost = input_cost + output_cost

        logger.debug(
            f"Cost calculation - Model: {model}, "
            f"Prompt tokens: {prompt_tokens}, "
            f"Completion tokens: {completion_tokens}, "
            f"Total cost: ${total_cost:.6f}"
        )

        return total_cost

    def get_model_pricing(self, model: str) -> dict:
        """Get pricing information for a specific model."""
        return self.pricing_data.get(model, {})

    def get_all_models(self) -> list:
        """Get list of all models with pricing data."""
        return list(self.pricing_data.keys())
