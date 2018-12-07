#!/usr/bin/env perl

use Modern::Perl;

use Mojo::UserAgent;
use Mojo::JSON qw(encode_json);

my ($login, $password, $destination) = @ARGV;

my $ua = Mojo::UserAgent->new;

$ua->websocket("ws://$login:$password\@127.0.0.127/v0/api" => sub {
	my ($ua, $tx) = @_;
	say 'WebSocket handshake failed!' and return unless $tx->is_websocket;
	my $request = sub {
		my $json = shift;
		say 'Request  : '.encode_json $json;
		$tx->send({ json => $json });
	};
	$tx->on(json => sub {
		my ($tx, $json) = @_;
		say 'Response : '.(encode_json $json);
		if ($json->{method} and $json->{method} eq 'OnTerminateCall') {
			$tx->finish;
		} elsif ($json->{result} and $json->{result}{data}) {
			if ($json->{id} == 1) {
				$request->({ id => 2, jsonrpc => '2.0', method => 'PlayAnouncement', 
					params => { call_session => $json->{result}{data}{call_session}, filename => 'welcome.pcm' }});
			} elsif ($json->{id} == 2) {
				$request->({ id => 3, jsonrpc => '2.0', method => 'TerminateCall', 
					params => { call_session => $json->{result}{data}{call_session} }});
			}
		}
	});
	$request->({ id => 1, jsonrpc => '2.0', method => 'MakeCall', params => { bnum => $destination }});
});

Mojo::IOLoop->start unless Mojo::IOLoop->is_running;
