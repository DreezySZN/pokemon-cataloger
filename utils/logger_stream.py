class LoggerStream:
    """Stream wrapper for redirecting stdout/stderr to logging."""
    
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
    
    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())
    
    def flush(self):
        pass