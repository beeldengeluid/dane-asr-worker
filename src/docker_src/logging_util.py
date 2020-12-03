import logging
import os

def init_logger(log_dir, log_name, log_level_console, log_level_file):
	logger = logging.getLogger(log_name)
	level_file = logging.getLevelName(log_level_file)
	level_console = logging.getLevelName(log_level_console)
	logger.setLevel(level_file)

	# create file handler which logs even debug messages
	if not os.path.exists(os.path.realpath(log_dir)):
		os.mkdir(os.path.realpath(log_dir))

	fh = logging.FileHandler(os.path.join(
		os.path.realpath(log_dir),
		log_name
	))
	fh.setLevel(level_file)

	# create console handler with a higher log level
	ch = logging.StreamHandler()
	ch.setLevel(level_console)

	# create formatter and add it to the handlers
	formatter = logging.Formatter(
		'%(asctime)s|%(levelname)s|%(process)d|%(module)s|%(funcName)s|%(lineno)d|%(message)s'
	)
	fh.setFormatter(formatter)
	ch.setFormatter(formatter)

	# add the handlers to the logger
	logger.addHandler(fh)
	logger.addHandler(ch)

	logger.info("Loaded logger")

	return logger