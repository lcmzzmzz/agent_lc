"""
OpenAlex学术文献检索器子模块。

【正经注释】本模块为OpenAlex检索器的子包初始化文件，负责导出OpenAlexSearch类，
供上层retrievers包统一引用。

【大白话注释】这个文件就是个"快递中转站"，把openalex.py里写好的OpenAlexSearch类
暴露出去，让外面的人能直接import来用。
"""
