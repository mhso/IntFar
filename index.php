<?php
$app_name = "intfar";

$ports_file = dirname(__DIR__) . "/flask_ports.json";
$ports_map = json_decode(file_get_contents($ports_file), true);
$port = $ports_map[$app_name];

$url = "https://mhooge.com:" . $port . "/" . $app_name;

$redir = "";
if ($_SERVER["REQUEST_URI"] != "/" . $app_name . "/") {
    $redir = $url."/".(explode("/", $_SERVER["REQUEST_URI"], 3)[2]);
}
else {
    $redir = $url;
}

header("Location: " . $redir);
?>