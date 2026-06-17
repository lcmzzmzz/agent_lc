"""
配置模块初始化文件。

【正经注释】
本模块负责导出配置管理的核心组件，包括 Config 配置管理类、
BaseConfig 类型定义以及 DefaultConfig 默认配置实例，
供外部模块统一导入使用。

【大白话注释】
这个文件就是个"导出窗口"，把配置相关的几个关键东西暴露出去，
外面想用配置的话，直接 from gpt_researcher.config import Config 就行了。
"""
from .config import Config  # 正经注释：导入配置管理主类 / 大白话注释：把配置大管家引进来
from .variables.base import BaseConfig  # 正经注释：导入基础配置类型定义 / 大白话注释：把配置的"字段表"引进来
from .variables.default import DEFAULT_CONFIG as DefaultConfig  # 正经注释：导入默认配置字典并起别名 / 大白话注释：把默认配置的"出厂设置"引进来，起了个短名

__all__ = ["Config", "BaseConfig", "DefaultConfig"]  # 正经注释：模块公开API列表，控制 from config import * 的导出范围 / 大白话注释：告诉别人这个模块对外提供哪几个东西
