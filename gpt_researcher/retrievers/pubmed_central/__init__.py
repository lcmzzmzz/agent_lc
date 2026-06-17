"""
PubMed Central生物医学文献检索器子模块。

【正经注释】本模块为PubMed Central检索器的子包初始化文件，负责导出PubMedCentralSearch类，
供上层retrievers包统一引用。

【大白话注释】这个文件就是个"快递中转站"，把pubmed_central.py里写好的PubMedCentralSearch类
暴露出去，让外面的人能直接import来用。
"""
