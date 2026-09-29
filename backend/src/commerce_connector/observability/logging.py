import json, logging
def get_logger(name): return logging.getLogger(name)
def configure_logging(level="INFO"):
    logging.basicConfig(level=getattr(logging,level.upper(),logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
def log_event(logger,event,**fields):
    logger.info(json.dumps({"event":event,**fields},default=str))
