from abc import ABC, abstractmethod
import scaledown

class BaseCompressor(ABC):
    def __init__(self, rate, api_key=None):
        """
        rate : float or 'auto', default='auto'
            The target rate of compression.
        """
        self.rate = rate
        self.api_key = api_key or scaledown.get_api_key()
        
    @abstractmethod
    def compress(self, context, prompt, max_tokens=None):
        """
        Compress the context relative to the prompt.

        Returns:
        CompressedPrompt
            A string subclass containing the compressed text. 
            Access metadata via .metrics property.
        """
        pass
