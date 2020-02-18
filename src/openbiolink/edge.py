from openbiolink.edgeType import EdgeType
from openbiolink.namespace import Namespace


class Edge:
    def __init__(self, id1: str, namespace1: Namespace, nodeType1, type: EdgeType, id2: str, namespace2: Namespace,
                 nodeType2, source: "", qScore=None, sourcedb=None):
        self.id1 = id1
        self.namespace1 = namespace1
        self.nodeType1 = nodeType1
        self.type = type
        self.id2 = id2
        self.namespace2 = namespace2
        self.nodeType2 = nodeType2
        self.source = source
        self.qScore = qScore
        self.sourcedb = sourcedb

    def __eq__(self, other):
        if isinstance(other, Edge):
            return (
                    self.type == other.type and self.id1 == other.id1 and self.id2 == other.id2
            )  # todo only if directional
        return False

    def __hash__(self):
        return hash((self.id1, self.type, self.id2))

    def __iter__(self):
        return iter([self.id1, self.type, self.id2, self.qScore])

    def to_list(self, include_qscore):
        if include_qscore:
            return iter([self.namespace1.resolve(self.id1), self.type,
                         self.namespace2.resolve(self.id2), self.qScore, self.sourcedb])
        else:
            return iter([self.namespace1.resolve(self.id1), self.type,
                         self.namespace2.resolve(self.id2), "", self.sourcedb])

    def to_sub_rel_obj_list(self):
        return iter([self.id1, self.type, self.id2, self.sourcedb])
