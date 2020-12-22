<?php
require 'vendor/autoload.php';
use GuzzleHttp\Client;
use GuzzleHttp\HandlerStack;
use GuzzleHttp\Handler\StreamHandler;

$url = "http://5500:mhooge.com/intfar";

$redir = "";
if ($_SERVER["REQUEST_URI"] != "/ngrok_redir/") {
    $redir = $url."/".(explode("/", $_SERVER["REQUEST_URI"], 3)[2]);
}
else {
    $redir = $url;
}

$headers = getallheaders();
$headers_str = [];

foreach ( $headers as $key => $value){
    if($key == 'Host')
        continue;
    $headers_str[]=$key.":".$value;
}

$handler = new StreamHandler();
$stack = HandlerStack::create($handler); // Wrap w/ middleware
$client = new Client(['handler' => $stack]);

$options = [
    "headers" => $headers_str,
    "http_errors" => false
];

file_put_contents("log.txt", print_r($redir, true) . "\n", FILE_APPEND);

$response = $client->request("POST", $redir, $options);

$body = $response->getBody();
$body->seek(0);
$text = $body->read(1024);
file_put_contents("log.txt", print_r($text, true) . "\n", FILE_APPEND);
echo $text;
?>