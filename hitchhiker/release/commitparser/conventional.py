import re
from typing import Optional
import hitchhiker.release.enums as enums


class ConventionalCommitParser:
    """Parses conventional commits"""

    # constants
    __FOOTER_REGEX = r"^((?:[a-zA-Z\-]+)|(?:BREAKING CHANGE))(?:(?:(: )(.+))|(?:( #)([0-9]+)))(?:[ ]*)$"
    __SUBJECT_REGEX = r"^([a-zA-Z]+)(?:\(([a-zA-Z]+)\))?(!)?: (.+)$"

    is_conventional: bool = False
    type: Optional[str] = None
    scope: Optional[str] = None
    breaking: Optional[bool] = None
    __message: str = ""

    def __init__(self, msg: str) -> None:
        """
        Initialize the class with the provided message and parse it.

        Parameters:
            msg (str): The message to be parsed.

        Returns:
            None
        """
        self.parse(msg)

    def __reset(self) -> None:
        """
        Reset the internal state of the object.

        Returns:
            None
        """
        self.is_conventional = False
        self.type = None
        self.scope = None
        self.breaking = None
        self.__message = ""

    def parse(self, msg: str) -> None:
        """
        Initializes this class with the commit message passed in msg, parsing its components.

        Parameters:
            msg (str): The commit message to be parsed.

        Returns:
            None
        """
        self.__reset()
        self.__message = msg
        match = re.match(self.__SUBJECT_REGEX, self.get_raw_subject(), re.DOTALL)
        if not match:
            return
        self.type = match.group(1)
        if self.type is not None:
            self.is_conventional = True
        self.scope = match.group(2)
        self.breaking = match.group(3) is not None
        if not self.breaking:
            for footer in self.get_footers():
                if footer[0] == "BREAKING CHANGE" or footer[0] == "BREAKING-CHANGE":
                    self.breaking = True
                    break

    def get_raw_subject(self) -> str:
        """
        Returns the subject of a commit from the stored commit message.

        Returns:
            str: The subject of the commit.

        Description:
        The subject is the first line of the commit message, typically summarizing the commit.
        """
        return self.__message.split("\n", 1)[0]

    def get_raw_body(self) -> str:
        """
        Returns the body of a commit from the stored commit message.

        Returns:
            str: The body of the commit.

        Description:
        The body is the part of the commit message that provides additional details or context
        beyond the subject, often describing the changes made in more detail.
        """
        split = self.__message.split("\n")
        if len(split) <= 1:
            return ""
        del split[0]
        return "\n".join(split)

    def get_description(self) -> str:
        """
        Returns the description of a conventional commit.

        Returns:
            str: The description of the conventional commit.

        Description:
        The description typically follows the subject in a conventional commit
        and provides additional information or details about the changes made.
        """
        match = re.match(self.__SUBJECT_REGEX, self.get_raw_subject(), re.DOTALL)
        if match is None:
            return self.get_raw_subject()
        return match.group(4)

    def get_body(self) -> str:
        """
        Returns the body of a conventional commit from the stored commit message.

        Returns:
            str: The body of the conventional commit.

        Description:
        The body of a conventional commit provides additional details or context
        beyond the subject and description, often describing the changes in more detail.
        """
        body = ""
        for line in self.get_raw_body().split("\n"):
            if re.match(self.__FOOTER_REGEX, line) is not None:
                break
            body += line + "\n"
        return body

    def get_footers(self) -> list[tuple[str, str, bool]]:
        """
        Returns the footers of a conventional commit in a structured format.

        Returns:
            list: A list of tuples in the format [(token, text, is_issue)].
                is_issue indicates whether the footer has the format 'name #123'.

        Description:
        The footers of a conventional commit provide additional metadata or references related to the commit.
        The method parses the footers from the raw body and returns them in a structured format.
        """
        footers = []  # (token, text, is_issue)
        footer_started = False
        for line in self.get_raw_body().split("\n"):
            match = re.match(self.__FOOTER_REGEX, line)
            if match is not None:
                footer_started = True
                token = match.group(1)
                text = match.group(3) if match.group(2) is not None else match.group(5)
                is_issue = match.group(4) is not None
                assert token is not None
                footers.append((token, text, is_issue))
            # assuming issue footer cannot be multiline?? - is this correct?
            # According to angular commit guidelines this is indeed the case but the conventional commits spec does not seem to mention this
            elif footer_started and not footers[-1][2]:
                footers[-1] = (
                    footers[-1][0],
                    footers[-1][1] + "\n" + line,
                    footers[-1][2],
                )
        return footers

    def get_version_bump(self) -> enums.VersionBump:
        """
        Returns the type of version bump this commit should trigger.

        Returns:
            VersionBump: The type of version bump (MAJOR, MINOR, PATCH, or NONE).

        Description:
        This method analyzes the commit properties and determines the appropriate version bump type.
        The version bump is based on conventional commit types and whether the commit represents a breaking change.
        """
        if self.breaking:
            return enums.VersionBump.MAJOR
        elif self.type in ["feat", "feature"]:
            return enums.VersionBump.MINOR
        elif self.type in ["fix"]:
            return enums.VersionBump.PATCH
        return enums.VersionBump.NONE
