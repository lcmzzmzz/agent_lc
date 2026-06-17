"""
Google搜索引擎检索器子模块。

【正经注释】本模块为Google检索器的子包初始化文件，负责导出GoogleSearch类，
供上层retrievers包统一引用。

【大白话注释】这个文件就是个"快递中转站"，把google.py里写好的GoogleSearch类
暴露出去，让外面的人能直接import来用。
"""
