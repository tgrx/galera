# ---------------------------------------------------------
# [  INCLUDES  ]
# override to whatever works on your system

include ./Makefile.in.mk


# ---------------------------------------------------------
# [  TARGETS  ]
# override to whatever works on your system

APPLICATION := main.webapp:application
ENTRYPOINT := $(PYTHON) $(DIR_SRC)/main/webapp.py

include ./Makefile.targets.mk


# ---------------------------------------------------------
# [  TARGETS  ]
# keep your targets here


.PHONY: migrate
migrate::
	$(PYTHON) -m main.db
