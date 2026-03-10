from abc import ABC, abstractmethod
from typing import Union, List, Optional
import scaledown

class BaseOptimizer(ABC):
    """
    Base class for all context optimizers.
    Optimizers process raw context before compression.
    """
    
    def __init__(self, api_key: Optional[str] = None, target_model:str="gpt-4o", **kwargs):
        """
        Initialize optimizer.
        
        Parameters
        ----------
        api_key : str, optional
            API key for optimizer services (if needed)
        **kwargs : dict
            Additional optimizer-specific parameters
        """
        self.api_key = api_key or scaledown.get_api_key()
        self.target_model = target_model
        self.config = kwargs
    
    @abstractmethod
    def optimize(
        self,
        context: Union[str, List[str]],
        query: Optional[str] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        Optimize context for better relevance and structure.
        
        Parameters
        ----------
        context : str or List[str]
            Raw context to optimize (e.g., codebase, documents)
        query : str, optional
            Query to guide optimization
        max_tokens : int, optional
            Maximum token budget for optimized context
        **kwargs : dict
            Additional optimization parameters
            
        Returns
        -------
        OptimizedContext or List[OptimizedContext]
            Optimized context with metrics
        """
        pass
    
    def update_config(self, **kwargs):
        """Update optimizer configuration."""
        self.config.update(kwargs)
