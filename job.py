class Job(object):
    """Job object to store title and description"""
    title: str
    description: str
    link: str

    def __init__(self, title: str, description: str, link: str):
        self.title = title
        self.description = description
        self.link = link
