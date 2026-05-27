"""
Multi-Agent Base Agent - 多智能体基础类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class Message:
    """智能体之间的消息"""
    sender: str
    receiver: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """任务"""
    id: str
    description: str
    status: str = "pending"  # pending, in_progress, done, failed
    assignee: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    dependencies: List[str] = field(default_factory=list)


class BaseAgent(ABC):
    """智能体基类"""

    def __init__(self, name: str, role: str, description: str):
        self.name = name
        self.role = role
        self.description = description
        self.messages: List[Message] = []
        self.tasks: List[Task] = []
        self.context: Dict[str, Any] = {}

    @abstractmethod
    def process_message(self, message: Message) -> Message:
        """处理收到的消息"""
        pass

    @abstractmethod
    def think(self) -> str:
        """思考并生成响应"""
        pass

    def send_message(self, receiver: str, content: str, metadata: Dict = None) -> Message:
        """发送消息"""
        msg = Message(
            sender=self.name,
            receiver=receiver,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(msg)
        return msg

    def receive_message(self, message: Message):
        """接收消息"""
        self.messages.append(message)
        self.context[message.sender] = message.content

    def add_task(self, task: Task):
        """添加任务"""
        self.tasks.append(task)

    def update_task_status(self, task_id: str, status: str, result: Dict = None):
        """更新任务状态"""
        for task in self.tasks:
            if task.id == task_id:
                task.status = status
                if result:
                    task.result = result
                break

    def get_pending_tasks(self) -> List[Task]:
        """获取待处理任务"""
        return [t for t in self.tasks if t.status in ["pending", "in_progress"]]

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name} ({self.role})>"
