"""
Factor Registry Module (Phase Extension, Section 34)
实现因子动态注册中心与批处理接口。
新增因子只需增加一个被 @FactorRegistry.register 装饰的类或函数，
即可自动纳入全套批处理计算、IC/Rank IC 与 Group Return 诊断。
"""
from typing import Dict, Type, List, Optional, Any, Callable
import pandas as pd
from src.factors.base_factor import BaseFactor
from src.factors.core_factors import MOM20Factor, REV5Factor, LOWVOL20Factor

class FactorRegistry:
    """
    因子注册与管理中心
    """
    _registry: Dict[str, Type[BaseFactor]] = {}
    _metadata: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register(cls, name: str, direction: int = 1, description: str = ""):
        """
        因子注册装饰器
        
        Args:
            name: 因子唯一标识符
            direction: 1 (越高越好) 或 -1 (越低越好)
            description: 因子金融经济学假设与逻辑描述
        """
        def decorator(subclass: Type[BaseFactor]):
            cls._registry[name] = subclass
            cls._metadata[name] = {
                'name': name,
                'direction': direction,
                'description': description,
                'class_name': subclass.__name__
            }
            return subclass
        return decorator

    @classmethod
    def get_factor(cls, name: str) -> BaseFactor:
        if name not in cls._registry:
            raise KeyError(f"Factor '{name}' not found in FactorRegistry. Available: {list(cls._registry.keys())}")
        return cls._registry[name]()

    @classmethod
    def list_factors(cls) -> List[Dict[str, Any]]:
        return list(cls._metadata.values())

    @classmethod
    def calculate_all(cls, df: pd.DataFrame, factor_names: Optional[List[str]] = None) -> pd.DataFrame:
        """
        对所有已注册因子进行批处理计算，输出统一长表。
        
        Args:
            df: 面板价格数据 (包含 date, asset, close_adj, ret_total 等)
            factor_names: 若指定则只计算子集，默认计算全部已注册因子
        """
        targets = factor_names or list(cls._registry.keys())
        out_dfs = []
        for f_name in targets:
            factor_inst = cls.get_factor(f_name)
            factor_out = factor_inst.process(df)
            out_dfs.append(factor_out)
            
        if out_dfs:
            return pd.concat(out_dfs, ignore_index=True)
        return pd.DataFrame(columns=['date', 'asset', 'factor', 'raw_value', 'value', 'is_valid', 'preprocessing_version'])

# 注册三大核心因子
FactorRegistry.register("MOM20", direction=1, description="20日动量因子")(MOM20Factor)
FactorRegistry.register("REV5", direction=1, description="5日反转因子 (已统一方向)")(REV5Factor)
FactorRegistry.register("LOWVOL20", direction=1, description="20日低波动因子 (已统一方向)")(LOWVOL20Factor)

# 注册可扩展样例因子 (证明Section 34自主扩展机制完备性)
class MOM5Factor(BaseFactor):
    def __init__(self):
        super().__init__(name="MOM5", direction=1)
    def calculate_raw(self, df: pd.DataFrame) -> pd.Series:
        return df.groupby('asset', group_keys=False).apply(lambda g: g['close_adj'] / g['close_adj'].shift(5) - 1.0)

FactorRegistry.register("MOM5", direction=1, description="5日超短期动量拓展因子")(MOM5Factor)

