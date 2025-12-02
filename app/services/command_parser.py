"""
命令解析器模块
用于解析评论中的bot命令
"""
import re
import logging
from typing import Optional, Tuple, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ReviewCommand:
    """审查命令数据类"""
    command: str  # 命令类型，如 "review"
    features: List[str]  # 功能列表：comment, review, status
    focus_areas: List[str]  # 审查重点


class CommandParser:
    """命令解析器"""

    def __init__(self, bot_username: Optional[str] = None):
        """
        初始化命令解析器

        Args:
            bot_username: Bot的用户名（可选）
        """
        self.bot_username = bot_username

    def parse_comment(self, comment_body: str) -> Optional[ReviewCommand]:
        """
        解析评论内容，识别bot命令

        支持的格式：
        - /review
        - @bot_username /review
        - @bot_username /review --features comment,status
        - @bot_username /review --focus security,performance

        Args:
            comment_body: 评论内容

        Returns:
            ReviewCommand对象，如果不是有效命令则返回None
        """
        if not comment_body:
            return None

        # 清理多余空白
        comment = comment_body.strip()

        # 检查是否包含 /review 命令
        if "/review" not in comment:
            return None

        # 如果配置了bot用户名，检查是否@了bot
        if self.bot_username:
            mention_pattern = rf"@{re.escape(self.bot_username)}"
            if not re.search(mention_pattern, comment):
                logger.debug(f"评论中未提及bot用户名 @{self.bot_username}")
                return None

        # 解析命令
        return self._parse_review_command(comment)

    def _parse_review_command(self, comment: str) -> Optional[ReviewCommand]:
        """
        解析 /review 命令

        Args:
            comment: 评论内容

        Returns:
            ReviewCommand对象
        """
        # 默认值
        features = ["comment"]  # 默认只发评论
        focus_areas = ["quality", "security", "performance", "logic"]  # 默认全部

        # 解析 --features 参数
        features_match = re.search(r"--features\s+(\S+)", comment)
        if features_match:
            features_str = features_match.group(1)
            features = [f.strip().lower() for f in features_str.split(",")]
            # 过滤无效的功能
            valid_features = ["comment", "review", "status"]
            features = [f for f in features if f in valid_features]
            if not features:
                features = ["comment"]  # 如果没有有效功能，使用默认值

        # 解析 --focus 参数
        focus_match = re.search(r"--focus\s+(\S+)", comment)
        if focus_match:
            focus_str = focus_match.group(1)
            focus_areas = [f.strip().lower() for f in focus_str.split(",")]
            # 过滤无效的重点
            valid_areas = ["quality", "security", "performance", "logic"]
            focus_areas = [f for f in focus_areas if f in valid_areas]
            if not focus_areas:
                focus_areas = ["quality", "security", "performance", "logic"]

        logger.info(f"解析到 /review 命令: features={features}, focus={focus_areas}")

        return ReviewCommand(
            command="review",
            features=features,
            focus_areas=focus_areas
        )

    def is_bot_command(self, comment_body: str) -> bool:
        """
        快速检查评论是否包含bot命令

        Args:
            comment_body: 评论内容

        Returns:
            是否包含bot命令
        """
        if not comment_body:
            return False

        # 检查是否包含命令前缀
        if not re.search(r"/\w+", comment_body):
            return False

        # 如果配置了bot用户名，必须@bot
        if self.bot_username:
            mention_pattern = rf"@{re.escape(self.bot_username)}"
            return bool(re.search(mention_pattern, comment_body))

        return True
