host := gar9m.snowman.lan
command_port := 80
upload_port := 9999

FROZEN = gar9m.mpy

all: $(FROZEN)

%.mpy: %.py
	mpy-cross -v $<

clean:
	$(RM) *.mpy

upload-all: $(patsubst %,upload-%,$(FROZEN))

upload: upload-gar9m.mpy

upload-%: %
	(echo "RECV:$<"; cat "$<") | nc -v -N $(host) $(upload_port)

test-button:
	curl -v -u "$(AUTH)" --data-binary '{"cmd":"button"}' -H 'Content-type: application/json' http://$(host):$(command_port)/command | json_pp

.PHONY: all clean upload upload-all test-button
