<?php

$url = "https://mhooge.com:5000/intfar";

$redir = "";
if ($_SERVER["REQUEST_URI"] != "/intfar/") {
    $redir = $url."/".(explode("/", $_SERVER["REQUEST_URI"], 3)[2]);
}
else {
    $redir = $url;
}

header("Location: " . $redir);
?>