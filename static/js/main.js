document.addEventListener('DOMContentLoaded', function() {
    // Обновление текущего времени
    function updateCurrentTime() {
        const now = new Date();
        const options = { 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit',
            hour12: false 
        };
        const timeString = now.toLocaleTimeString('ru-RU', options);
        
        const timeElements = document.querySelectorAll('.current-time');
        timeElements.forEach(el => {
            el.textContent = timeString;
        });
    }
    
    // Инициализация подсказок
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    if (tooltipTriggerList.length > 0) {
        const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    }
    
    // Инициализация всплывающих окон
    const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
    if (popoverTriggerList.length > 0) {
        const popoverList = [...popoverTriggerList].map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));
    }
    
    // Обновление времени каждую секунду
    updateCurrentTime();
    setInterval(updateCurrentTime, 1000);
    
    // Подтверждение удаления
    const deleteButtons = document.querySelectorAll('.confirm-delete');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Вы уверены, что хотите удалить этот элемент?')) {
                e.preventDefault();
            }
        });
    });
    
    // Копирование текста в буфер обмена
    const copyButtons = document.querySelectorAll('.copy-text');
    copyButtons.forEach(button => {
        button.addEventListener('click', function() {
            const textToCopy = this.getAttribute('data-copy-text');
            navigator.clipboard.writeText(textToCopy).then(() => {
                // Показать уведомление об успешном копировании
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="fas fa-check"></i> Скопировано';
                
                setTimeout(() => {
                    this.innerHTML = originalText;
                }, 2000);
            }).catch(err => {
                console.error('Ошибка при копировании текста: ', err);
            });
        });
    });
});