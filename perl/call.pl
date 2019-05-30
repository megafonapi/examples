#!/usr/bin/env perl

use Modern::Perl;

use Mojo::UserAgent;
use Mojo::JSON qw(encode_json);

my ($login, $password, $destination) = @ARGV;

my $ua = Mojo::UserAgent->new;

my $id = 0;

$ua->websocket("wss://$login:$password\@testapi.megafon.ru/v1/api" => sub {
	my ($ua, $tx) = @_;
	say 'WebSocket handshake failed!' and return unless $tx->is_websocket;
	my $request = sub {
		my ($method, $params) = @_;
		my $json = { id => $id++, jsonrpc => '2.0', method => $method, params => $params };
		say 'Request  : '.encode_json $json;
		$tx->send({ json => $json });
	};
	$tx->on(json => sub {
		my ($tx, $json) = @_;
		say 'Response : '.(encode_json $json);
		if ($json->{method} and $json->{method} eq 'OnAnswerCall') {
			$request->('PlayAnnouncement', { call_session => $json->{params}{call_session}, filename => 'welcome.pcm' });
		} elsif ($json->{method} and $json->{method} eq 'OnPlayAnnouncement') {
			$request->('TerminateCall', { call_session => $json->{params}{call_session} });
		} elsif ($json->{method} and $json->{method} eq 'OnTerminateCall') {
			$tx->finish;
		}
	});
	$request->('MakeCall', { bnum => $destination });
});

Mojo::IOLoop->start unless Mojo::IOLoop->is_running;
