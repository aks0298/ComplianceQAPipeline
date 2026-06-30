'''
start->index_video_node->audit_content_node->end
'''

from langgraph.graph import StateGraph, START,END

from backend.src.graph.states import VideoAuditState

from backend.src.graph.nodes import index_video_node,audio_content_node

def create_graph():
    '''
    constructs and compile the grapg workflow
    return 
    compiled graph
    '''

    graph=StateGraph(VideoAuditState)

    graph.add_node("indexer", index_video_node)
    graph.add_node("auditor", audio_content_node)
    
    graph.add_edge(START, "indexer")
    graph.add_edge("indexer", "auditor")
    graph.add_edge("auditor", END)   

    return graph.compile()

app=create_graph()








